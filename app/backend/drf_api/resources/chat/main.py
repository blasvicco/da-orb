"""DRF chat viewset"""

# General imports
import logging
import threading
from datetime import UTC, datetime

# Lib imports
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

# App imports
from drf_api.models import MChatMessage, MChatSession, MUsageEvent
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.chat.permission import PChat, PN8nCallback
from drf_api.resources.chat.serializer import SChatMessage, SChatSession, SN8nCallback
from web_socket.helpers.n8n import (
	N8nClient,
	N8nQueueState,
	N8nSessionState,
	collect_execution_tree_usage,
)

_logger = logging.getLogger(__name__)

# Every v14 workflow Chat Model node uses the same model — collect_execution_tree_usage
# sums raw token counts from n8n's execution data, which never records which model
# produced them, so this is asserted here rather than threaded through the whole walk.
_USAGE_MODEL_NAME = "gpt-5-mini"


class _DictShim:
	"""Minimal stand-in exposing .to_dict()/.safe_to_dict()."""

	# Used to re-fire a queued message outside the original WebSocket connection —
	# org/user were captured as plain dicts when queued since this callback has no
	# access to that connection's live auth/session.

	def __init__(self, data):
		self._data = data or {}

	def safe_to_dict(self):
		"""Return the wrapped dict — already sanitised at capture time, so this is an alias."""
		return self._data

	def to_dict(self):
		"""Return the wrapped dict."""
		return self._data


async def _persist_n8n_state(group_name, *, merged):
	"""Save n8n session state to Redis so the next consumer fire reads fresh values."""
	state = N8nSessionState(group_name=group_name)
	try:
		await state.save(
			active_node_id=merged.get("active_node_id"),
			intention_nodes=merged.get("intention_nodes"),
			last_bot_message=merged.get("last_bot_message"),
		)
	finally:
		await state.close()


async def _load_n8n_state(group_name):
	"""Load current n8n session state from Redis."""
	state_store = N8nSessionState(group_name=group_name)
	try:
		return await state_store.load()
	finally:
		await state_store.close()


def _validate_callback_payload(data):
	"""Validate and curate n8n_callback's raw payload via SN8nCallback; raises on malformed input."""
	serializer = SN8nCallback(data=data)
	serializer.is_valid(raise_exception=True)
	validated = serializer.validated_data
	return (
		validated["group_name"],
		validated["text"],
		validated["type"],
		validated["extra"] or {},
		validated["state"] or {},
		validated["session_id"],
		validated["processes"],
		validated["root_execution_id"],
	)


def _resolve_and_persist_state(group_name, incoming):
	"""Merge incoming state with current Redis state and persist; return effective state."""
	# Null fields in the incoming payload (e.g. sent by n8n on MCP errors) do not
	# overwrite non-null values already saved in Redis, preserving user progress —
	# unless incoming.reset_process is True, which means n8n is intentionally
	# clearing the active process (e.g. parking it before asking the user whether
	# to resume), in which case null must be allowed to actually clear the stored
	# value instead of being coalesced back to the stale one.
	current = async_to_sync(_load_n8n_state)(group_name)
	if not incoming:
		return current
	reset_process = incoming.get("reset_process") is True

	def _merge_field(key, default=None, resettable=False):
		"""Prefer incoming[key] when present; otherwise fall back to current[key]."""
		# A resettable field additionally lets an explicit null through once
		# reset_process is set, so a handler can intentionally clear it instead of
		# null being coalesced back to the stale value already in Redis.
		if resettable and reset_process:
			return incoming.get(key, default)
		value = incoming.get(key)
		return value if value is not None else current.get(key, default)

	merged = {
		"active_node_id": _merge_field("active_node_id", resettable=True),
		"intention_nodes": _merge_field("intention_nodes", default={}),
		"last_bot_message": _merge_field("last_bot_message", resettable=True),
	}
	async_to_sync(_persist_n8n_state)(group_name, merged=merged)
	return merged


def _active_node(effective_state):
	"""Return the currently active intention_nodes entry, or {} if none.

	intention_nodes is keyed by each node's own id — the single source of truth for its
	process_id/process_definition/form_state, no separate root-level copy anymore.
	"""
	state = effective_state or {}
	return (state.get("intention_nodes") or {}).get(state.get("active_node_id")) or {}


def _resolve_process_name(effective_state, processes):
	"""Return the best available human-readable process name for this callback."""
	active_node = _active_node(effective_state)
	process_definition = active_node.get("process_definition") or {}
	# process_id is the process definition's opaque numeric key, not a display
	# name — prefer the definition's own name, then the disambiguation list's
	# name, and only fall back to the raw id if neither is available.
	return (
		process_definition.get("name")
		or (processes[0]["name"] if processes else "")
		or str(active_node.get("process_id") or "")
	)


def _collect_and_record_usage(*, process_name, root_execution_id, session_id):
	"""Background-thread entry point: wait for the whole execution tree to finish, then record its token usage."""
	# Runs off the request/response cycle entirely (see its threading.Thread call site) —
	# collect_execution_tree_usage polls for up to _POLL_TIMEOUT_SECONDS, which would
	# otherwise hold the n8n callback's own HTTP connection open needlessly; n8n's
	# "Django Callback" node doesn't wait on this response for anything.
	usage = collect_execution_tree_usage(root_execution_id)
	if usage is None:
		return
	try:
		session = MChatSession.objects.get(id=session_id)
	except MChatSession.DoesNotExist:
		return
	MUsageEvent.objects.create(
		completion_tokens=usage.get("completion_tokens"),
		connection_key=session.connection_key,
		event_type="token_usage",
		model_name=_USAGE_MODEL_NAME,
		occurred_on=datetime.now(UTC),
		org=session.org,
		process_name=process_name,
		prompt_tokens=usage.get("prompt_tokens"),
		session=session,
		total_tokens=usage.get("total_tokens"),
		username=session.username,
	)


def _record_usage_events(
	session, *, effective_state, occurred_on, processes, root_execution_id
):
	"""Persist a process-execution event if a process was involved, and kick off background token-usage collection."""
	has_process = bool(processes or _active_node(effective_state))
	process_name = (
		_resolve_process_name(effective_state, processes) if has_process else ""
	)
	if has_process:
		MUsageEvent.objects.create(
			connection_key=session.connection_key,
			event_type="process_execution",
			occurred_on=occurred_on,
			org=session.org,
			process_name=process_name,
			session=session,
			username=session.username,
		)
	if root_execution_id:
		# Fire-and-forget: this callback's own HTTP response to n8n ("Django Callback",
		# neverError) doesn't need to wait on this, and collect_execution_tree_usage's
		# own poll can take several seconds.
		threading.Thread(
			daemon=True,
			target=_collect_and_record_usage,
			kwargs={
				"process_name": process_name,
				"root_execution_id": root_execution_id,
				"session_id": session.id,
			},
		).start()


async def _release_and_refire(group_name):
	"""Release the in-flight lock for this chat and fire whatever was queued behind it."""
	# Runs synchronously within the n8n callback request (n8n is waiting on this HTTP
	# response), so this makes a single fire attempt with no retry/backoff — unlike
	# the consumer's own retry loop, retrying here would stall n8n's own callback.
	# On failure the queued message is dropped rather than left stuck; the user can
	# resend if that happens.
	queue = N8nQueueState(group_name=group_name)
	try:
		await queue.release()
		pending = await queue.pop_pending()
		if not pending:
			return
		if not await queue.try_start():
			# Another execution already started for this chat in the meantime —
			# put it back rather than silently dropping it.
			await queue.set_pending(pending)
			return
		client = N8nClient()
		state = N8nSessionState(group_name=group_name)
		try:
			await client.fire(
				expertise_level=pending["expertise_level"],
				group_name=pending.get("group_name", group_name),
				language=pending.get("language"),
				message=pending.get("message"),
				organization=_DictShim(pending.get("organization")),
				session_id=pending.get("session_id"),
				state=state,
				user=_DictShim(pending.get("user")),
			)
		except Exception:  # pylint: disable=broad-except
			_logger.exception(
				"_release_and_refire: failed to fire queued message for %s", group_name
			)
			await queue.release()
		finally:
			await state.close()
	finally:
		await queue.close()


class VSChat(viewsets.ViewSet):
	"""Chat View Set — session list, message history, session deletion, and n8n callback."""

	authentication_classes = []
	permission_classes = [PChat]

	@action(detail=False, methods=["delete"])
	def delete_session(self, request, *args, **kwargs):
		"""Delete a session and all its messages (org + connection_key scoped; ownership checked via permission)."""
		session_id = request.query_params.get("session_id")
		org, _, connection_key = self._get_org_and_user(request)
		session = get_object_or_404(
			MChatSession, connection_key=connection_key, id=session_id, org=org
		)
		self.check_object_permissions(request, session)
		session.delete()
		return Response(status=204)

	@action(detail=False, methods=["get"])
	def messages(self, request, *args, **kwargs):
		"""Return all messages for a single session (validates org + username + connection_key ownership)."""
		session_id = request.query_params.get("session_id")
		org, username, connection_key = self._get_org_and_user(request)
		session = get_object_or_404(
			MChatSession,
			connection_key=connection_key,
			id=session_id,
			org=org,
			username=username,
		)
		return Response(SChatMessage(session.messages.all(), many=True).data)

	@action(detail=False, methods=["post"], permission_classes=[PN8nCallback])
	def n8n_callback(self, request, *args, **kwargs):
		"""Receive an async result from the n8n workflow and push it to the WebSocket group."""
		# Expected payload from n8n:
		#   group_name         – channel group to broadcast to, scoped per chat (e.g. "chat_<org>_<user>_<chat_key>")
		#   session_id         – MChatSession pk (for DB persistence; ignored for type "status")
		#   text               – reply text
		#   type               – message type: "agent" | "alert" | "system" | "status"
		#   extra              – optional dict merged into the broadcast payload
		#   state              – optional dict with active_node_id / intention_nodes to persist in Redis
		#   processes          – optional list; when present, signals the consumer to store them
		#                       as pending_processes for the next disambiguation reply
		#   root_execution_id  – optional; this turn's spine execution id, used to walk the whole
		#                       execution tree and record token usage in the background once it's
		#                       confirmed done (see _collect_and_record_usage)
		#
		# "status" messages are ephemeral: they are broadcast to the WebSocket group but
		# never persisted to the database, and they do not update Redis state.
		(
			group_name,
			text,
			msg_type,
			extra,
			state,
			session_id,
			processes,
			root_execution_id,
		) = _validate_callback_payload(request.data)

		if processes:
			extra["processes"] = processes

		# Status messages are ephemeral — skip state merging and persistence.
		effective_state = (
			None
			if msg_type == "status"
			else _resolve_and_persist_state(group_name, state)
		)

		payload = {
			"text": text,
			"time": datetime.now(UTC).isoformat(),
			"type": msg_type,
		}
		if extra:
			payload.update(extra)
		# Always include the effective process state so the frontend can recover from errors.
		if effective_state:
			payload["state"] = effective_state

		async_to_sync(get_channel_layer().group_send)(
			group_name, {"type": "broadcast", "payload": payload}
		)

		# Tell the consumer to store the process list for the next disambiguation reply.
		if processes:
			async_to_sync(get_channel_layer().group_send)(
				group_name, {"type": "set_processes", "processes": processes}
			)

		# Persist the message and n8n state to the database.
		# Status messages are ephemeral and must not be persisted.
		if msg_type != "status" and session_id:
			try:
				session = MChatSession.objects.get(id=session_id)
				MChatMessage.objects.create(
					session=session,
					type=msg_type,
					text=text,
					extra=extra or None,
					timestamp=datetime.fromisoformat(payload["time"]),
				)
				if state:
					MChatSession.objects.filter(pk=session.pk).update(
						n8n_state=effective_state
					)
				_record_usage_events(
					session,
					effective_state=effective_state,
					occurred_on=datetime.fromisoformat(payload["time"]),
					processes=processes,
					root_execution_id=root_execution_id,
				)
			except MChatSession.DoesNotExist:
				pass

		# This is a terminal result ("agent"/"alert", not an ephemeral "status" ping) —
		# release this chat's in-flight lock and fire whatever was queued behind it.
		if msg_type != "status":
			async_to_sync(_release_and_refire)(group_name)

		return Response(status=200)

	@action(detail=False, methods=["get"])
	def sessions(self, request, *args, **kwargs):
		"""Return the 15 most-recent chat sessions for the requesting user."""
		org, username, connection_key = self._get_org_and_user(request)
		if org is None or not username:
			return Response([])
		qs = MChatSession.objects.filter(
			connection_key=connection_key, org=org, username=username
		).annotate(
			tokens_used=Sum(
				"usage_events__total_tokens",
				filter=Q(usage_events__event_type="token_usage"),
			)
		)[
			:15
		]
		return Response(SChatSession(qs, many=True).data)

	def _get_org_and_user(self, request):
		"""Return (org, username, connection_key) from the request context."""
		return resolve_request_identity(request)
