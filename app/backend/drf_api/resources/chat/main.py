"""DRF chat viewset"""

# General imports
import logging
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
from drf_api.resources.chat.serializer import SChatMessage, SChatSession
from web_socket.helpers.n8n import N8nClient, N8nQueueState, N8nSessionState

_logger = logging.getLogger(__name__)


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
			awaiting_batch_confirmation=merged.get(
				"awaiting_batch_confirmation", False
			),
			awaiting_stack_resume=merged.get("awaiting_stack_resume", False),
			form_state=merged.get("form_state"),
			intention_nodes=merged.get("intention_nodes"),
			last_bot_message=merged.get("last_bot_message"),
			parent_override_id=merged.get("parent_override_id"),
			paused_node_ids=merged.get("paused_node_ids"),
			pending_batch_items=merged.get("pending_batch_items"),
			pending_processes=merged.get("pending_processes"),
			process_definition=merged.get("process_definition"),
			process_id=merged.get("process_id"),
			process_stack=merged.get("process_stack"),
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
		"awaiting_batch_confirmation": _merge_field(
			"awaiting_batch_confirmation", default=False
		),
		"awaiting_stack_resume": _merge_field("awaiting_stack_resume", default=False),
		"form_state": _merge_field("form_state", resettable=True),
		"intention_nodes": _merge_field("intention_nodes", default=[]),
		"last_bot_message": _merge_field("last_bot_message", resettable=True),
		# Gated the same as active_node_id/process_id (not a plain pass-through):
		# Decode & Set Process consumes this exactly when it resolves a new node,
		# which is also when it sets reset_process, so the same reset_process gate
		# that lets process_id/active_node_id be explicitly cleared to null also
		# lets this one-shot override be explicitly cleared once consumed.
		"parent_override_id": _merge_field("parent_override_id", resettable=True),
		"paused_node_ids": _merge_field("paused_node_ids", default=[]),
		"pending_batch_items": _merge_field("pending_batch_items", default=[]),
		"pending_processes": _merge_field("pending_processes"),
		"process_definition": _merge_field("process_definition", resettable=True),
		"process_id": _merge_field("process_id", resettable=True),
		"process_stack": _merge_field("process_stack", default=[]),
	}
	async_to_sync(_persist_n8n_state)(group_name, merged=merged)
	return merged


def _resolve_process_name(effective_state, processes):
	"""Return the best available human-readable process name for this callback."""
	process_definition = (effective_state or {}).get("process_definition") or {}
	# process_id is the process definition's opaque numeric key, not a display
	# name — prefer the definition's own name, then the disambiguation list's
	# name, and only fall back to the raw id if neither is available.
	return (
		process_definition.get("name")
		or (processes[0]["name"] if processes else "")
		or str((effective_state or {}).get("process_id") or "")
	)


def _record_usage_events(session, *, effective_state, extra, occurred_on, processes):
	"""Persist token-usage and/or process-execution events for this callback, if present."""
	has_process = bool(
		processes or (effective_state and effective_state.get("process_id"))
	)
	process_name = (
		_resolve_process_name(effective_state, processes) if has_process else ""
	)

	# Token-usage events depend on n8n's "Build Callback Payload" node forwarding a
	# usage sub-object inside extra, summed from the OpenAI Chat Model nodes'
	# tokenUsageEstimate output. Left None-safe since callers without that node
	# change (or callbacks with no usage to report) simply omit the key.
	usage = extra.get("usage")
	if usage:
		MUsageEvent.objects.create(
			completion_tokens=usage.get("completion_tokens"),
			connection_key=session.connection_key,
			event_type="token_usage",
			model_name=usage.get("model", ""),
			occurred_on=occurred_on,
			org=session.org,
			process_name=process_name,
			prompt_tokens=usage.get("prompt_tokens"),
			session=session,
			total_tokens=usage.get("total_tokens"),
			username=session.username,
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
				active_node_override=pending.get("active_node_override"),
				expertise_level=pending.get("expertise_level", 2),
				group_name=pending.get("group_name", group_name),
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
		#   group_name  – channel group to broadcast to, scoped per chat (e.g. "chat_<org>_<user>_<chat_key>")
		#   session_id  – MChatSession pk (for DB persistence; ignored for type "status")
		#   text        – reply text
		#   type        – message type: "agent" | "alert" | "system" | "status"
		#   extra       – optional dict merged into the broadcast payload
		#   state       – optional dict with form_state / process_id to persist in Redis
		#   processes   – optional list; when present, signals the consumer to store them
		#                as pending_processes for the next disambiguation reply
		#
		# "status" messages are ephemeral: they are broadcast to the WebSocket group but
		# never persisted to the database, and they do not update Redis state.
		group_name = request.data.get("group_name", "")
		text = request.data.get("text", "")
		msg_type = request.data.get("type", "agent")
		extra = request.data.get("extra") or {}
		state = request.data.get("state") or {}
		session_id = request.data.get("session_id")
		processes = request.data.get("processes")

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

		layer = get_channel_layer()
		async_to_sync(layer.group_send)(
			group_name, {"type": "broadcast", "payload": payload}
		)

		# Tell the consumer to store the process list for the next disambiguation reply.
		if processes:
			async_to_sync(layer.group_send)(
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
					extra=extra,
					occurred_on=datetime.fromisoformat(payload["time"]),
					processes=processes,
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
