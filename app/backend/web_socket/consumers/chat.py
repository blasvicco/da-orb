"""Chat Web socket module"""

# General imports
import asyncio
from datetime import datetime, UTC
import logging
import uuid

# Lib imports
from channels.db import database_sync_to_async
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Sum

# App imports
from drf_api.models import MBucketFile, MChatMessage, MChatSession, MProject
from web_socket.helpers.n8n import (
	N8nClient,
	N8nClientError,
	N8nQueueState,
	N8nSessionState,
)
from web_socket.serializers import SActiveNodeSwitch, SMessageSend
from .abstract import CAbstract

_logger = logging.getLogger(__name__)

_BYTES_PER_MB = 1024 * 1024

_MSG_AGENT_ERROR = "chat.system.agentError"
_MSG_AGENT_UNAVAILABLE = "chat.system.agentUnavailable"
_MSG_BATCH_TOO_LARGE = "chat.system.batchTooLarge"
_MSG_QUEUED = "chat.system.queued"


# DB helpers


@database_sync_to_async
def _create_session(connection_key, org, project, username):
	return MChatSession.objects.create(
		connection_key=connection_key, org=org, project=project, username=username
	)


@database_sync_to_async
def _load_session(connection_key, org_id, session_id, username):
	try:
		return MChatSession.objects.get(
			connection_key=connection_key,
			deleted_on__isnull=True,
			id=session_id,
			org_id=org_id,
			username=username,
		)
	except MChatSession.DoesNotExist:
		return None


@database_sync_to_async
def _resolve_project(connection_key, org, project_id, username):
	return MProject.resolve_for_chat(org, username, connection_key, project_id)


@database_sync_to_async
def _save_message(session, msg_type, text, extra, iso_time):
	MChatMessage.objects.create(
		session=session,
		type=msg_type,
		text=text,
		extra=extra or None,
		timestamp=datetime.fromisoformat(iso_time),
	)


@database_sync_to_async
def _set_session_title(session, title):
	MChatSession.objects.filter(pk=session.pk).update(title=title)
	session.title = title


@database_sync_to_async
def _sum_bucket_file_sizes(file_ids, session):
	return (
		MBucketFile.objects.filter(id__in=file_ids, session=session).aggregate(
			total=Sum("size")
		)["total"]
		or 0
	)


# Consumer


class CChat(CAbstract):  # pylint: disable=too-many-instance-attributes
	"""Chat web socket class"""

	chat_session = None
	connection_key = ""
	group_name_prefix = "chat"
	n8n_client = None
	n8n_state = None
	n8n_queue = None
	organization = None
	pending_processes = None
	_resume_project_id = None
	_resume_session_id = None
	_new_chat_token = None

	def get_group_name(self):
		"""Get group name implementation."""
		# Scoped per (org, user, chat) — not just (org, user) — so a user can have
		# multiple chats open and in progress at once without their n8n session
		# state (and WS broadcast routing) colliding. When resuming an existing
		# chat, the chat's own session_id keys the group. For a brand-new chat,
		# the session_id doesn't exist yet (it's created lazily on first message),
		# so a per-connection random token is generated instead — stable for the
		# lifetime of this connection and never shared with another tab/chat.
		if self._resume_session_id:
			chat_key = self._resume_session_id
		else:
			if not self._new_chat_token:
				self._new_chat_token = uuid.uuid4().hex
			chat_key = self._new_chat_token
		return f"{self.group_name_prefix}_{self.organization.id}_{self.user.username}_{chat_key}"

	def _get_auth_ok_extra(self):
		return {"session_id": self.chat_session.id} if self.chat_session else {}

	async def auth_init(self, content):
		"""Capture optional session_id for resume, and project_id for a new chat, before delegating to parent."""
		project_id = content.get("project_id")
		# Only a real integer id is accepted — anything else falls back to the Default project.
		self._resume_project_id = project_id if isinstance(project_id, int) else None
		self._resume_session_id = content.get("session_id")
		await super().auth_init(content)

	def _resolve_process_selection(self, message_text):
		"""If the user replied with a number or letter, map it to the corresponding process name."""
		if not self.pending_processes:
			return message_text

		text = message_text.strip()
		lower = text.lower()
		resolved = None

		if text.isdigit():
			idx = int(text) - 1
			if 0 <= idx < len(self.pending_processes):
				resolved = self.pending_processes[idx]["name"]
		elif len(lower) == 1 and lower.isalpha():
			idx = ord(lower) - ord("a")
			if 0 <= idx < len(self.pending_processes):
				resolved = self.pending_processes[idx]["name"]

		self.pending_processes = None
		return resolved or message_text

	async def _broadcast(self, text, msg_type, extra=None):
		"""Send a message payload to the channel group and persist to DB."""
		payload = {
			"text": text,
			"time": datetime.now(UTC).isoformat(),
			"type": msg_type,
		}
		if extra:
			payload.update(extra)
		await self.channel_layer.group_send(
			self.group_name,
			{"payload": payload, "type": "broadcast"},
		)
		# Persist everything shown in the chat history — only "status" is a purely
		# ephemeral typing-indicator ping that never becomes a bubble in the first place.
		if self.chat_session and msg_type != "status":
			try:
				await _save_message(
					self.chat_session, msg_type, text, extra, payload["time"]
				)
			except IntegrityError:
				_logger.warning(
					"Session %s deleted before message could be saved.",
					self.chat_session.pk,
				)
				self.chat_session = None

	async def _ensure_session(self):
		"""Create the DB session if one doesn't exist yet, and notify the frontend."""
		# Idempotent and safe to call ahead of any real message — e.g. right when a
		# file is attached to a brand-new chat, so the upload has a real session_id
		# to target instead of silently deferring until the first message is sent.
		if self.chat_session is not None:
			return
		# The project the frontend had selected when it connected (or the Default project
		# if none/unknown/deleted) — only ever consulted here, never when resuming a session.
		project = await _resolve_project(
			connection_key=self.connection_key,
			org=self.organization,
			project_id=self._resume_project_id,
			username=self.user.username,
		)
		self.chat_session = await _create_session(
			connection_key=self.connection_key,
			org=self.organization,
			project=project,
			username=self.user.username,
		)
		await self._rekey_group()
		await self.send_json(
			{"type": "session.created", "session_id": self.chat_session.id}
		)

	async def _rekey_group(self):
		"""Migrate this connection to the deterministic, session-id-keyed group name
		now that a real session exists. A brand-new chat's group name (used before any
		session_id exists) is a random per-connection token; without this, a reconnect
		that later resumes this same session — e.g. the user switches to another chat
		and back before the reply arrives — computes the deterministic session-id name
		instead, never the original token. The in-flight reply's n8n callback would then
		broadcast into a group with no members (silently dropping the live update until
		a hard refresh), and its n8n_state/n8n_queue Redis keys would stay split across
		the two group names instead of serializing through the same lock/state bucket."""
		old_group_name = self.group_name
		self._resume_session_id = self.chat_session.id
		new_group_name = self.get_group_name()
		if new_group_name == old_group_name:
			return
		await self.channel_layer.group_add(new_group_name, self.channel_name)
		await self.channel_layer.group_discard(old_group_name, self.channel_name)
		self.group_name = new_group_name
		await self.n8n_state.close()
		await self.n8n_queue.close()
		self.n8n_state = N8nSessionState(group_name=new_group_name)
		self.n8n_queue = N8nQueueState(group_name=new_group_name)

	async def session_ensure(self, content):  # pylint: disable=unused-argument
		"""WS entry point: create the session ahead of a real message. Lets a file
		attached before anything is typed upload against a real session_id right
		away, instead of the message that follows carrying no bucket_file_ids."""
		await self._ensure_session()

	async def active_node_switch(self, content):
		"""WS entry point: switch the active Intention Graph node immediately, triggered
		by the user clicking a node in the sidebar and confirming the context switch.
		Resolved directly against Redis here — parks whatever was active, activates the
		target — with no n8n round-trip. n8n never needs to know how or why the active
		node changed; it only ever sees the result, already resolved, on whatever message
		comes next. Mirrors what Resolve Override (intent-manager.json) did before this
		moved out of n8n entirely.

		The announcement bubble the frontend shows for this switch is broadcast from here
		(as a "system" message) rather than pushed straight into the frontend's local message
		list, so it round-trips through _broadcast() and gets persisted like every other
		visible bubble — otherwise reopening the session for review loses all record of
		when/where the user jumped between intention-graph nodes."""
		serializer = SActiveNodeSwitch(data=content)
		if not serializer.is_valid():
			_logger.warning(
				"active_node_switch: rejected malformed payload: %s", serializer.errors
			)
			return
		target_id = serializer.validated_data["active_node_id"]
		if not target_id:
			return
		current = await self.n8n_state.load()
		nodes = current.get("intention_nodes") or {}
		target = nodes.get(target_id)
		if not target or target_id == current.get("active_node_id"):
			# Unknown/stale id, or already the active node — nothing to switch.
			return
		updated_nodes = dict(nodes)
		old_active_id = current.get("active_node_id")
		if (
			old_active_id
			and old_active_id in updated_nodes
			and updated_nodes[old_active_id].get("status") == "active"
		):
			# Only an actually-active node gets parked — a completed/failed node that
			# active_node_id happens to still point at (e.g. Compute Execution Outcome
			# deliberately leaves it there post-success) must not be relabeled "paused";
			# that would corrupt its terminal status for no reason.
			updated_nodes[old_active_id] = {
				**updated_nodes[old_active_id],
				"status": "paused",
			}
		# Only a genuinely resumable node (failed/paused, per UC-6) gets reactivated to
		# "active" — a completed/abandoned node stays exactly as it is; active_node_id
		# still moves to it so context questions ("why did this...", general_inquiry) can
		# reference it, but its own status is never disturbed. Without this guard, a
		# process_definition pruned down to {name} on completion (see
		# register-intention-node.json / sap-inquiry-execution.json) could get routed back
		# into form-filling with nothing to fill from.
		target_status = target.get("status")
		new_target_status = (
			"active" if target_status in ("failed", "paused") else target_status
		)
		updated_nodes[target_id] = {**target, "status": new_target_status}
		await self.n8n_state.save(
			active_node_id=target_id,
			intention_nodes=updated_nodes,
			last_bot_message=current.get("last_bot_message"),
		)
		text = serializer.validated_data["text"]
		if text:
			await self._broadcast(text, "system")

	async def message_send(self, content):
		"""Handle message sent by user"""
		serializer = SMessageSend(data=content)
		if not serializer.is_valid():
			_logger.warning(
				"message_send: rejected malformed payload: %s", serializer.errors
			)
			return
		validated = serializer.validated_data
		message_text = validated["message"].strip()
		resolved_text = self._resolve_process_selection(message_text)
		# One-shot references to bucket files attached as context for this turn —
		# explicitly picked via "Use as context", and/or files dropped onto the
		# composer and uploaded alongside this message. Forwarded to n8n as-is,
		# never resolved/embedded here (see upload_and_file_bucket.md §5).
		bucket_file_ids = validated["bucket_file_ids"]
		# The frontend's current UI locale, sent on every message — never defaulted here,
		# the user can switch it mid-conversation and every turn must reflect exactly
		# what they had selected when they hit send.
		language = validated["language"]

		# Lazily create the DB session on the first message to avoid empty orphan
		# records — may already exist here if session_ensure() ran earlier this
		# connection (e.g. a file was attached before anything was typed).
		await self._ensure_session()
		if not self.chat_session.title:
			# Set title BEFORE the sessions list next reflects it — no separate
			# notification needed here, session.created (if any) already fired
			# inside _ensure_session().
			await _set_session_title(self.chat_session, message_text[:80])
		elif resolved_text != message_text:
			# User resolved a process selection (e.g. "1" → "Create Purchase Request").
			# Use the resolved process name as a more meaningful session title.
			await _set_session_title(self.chat_session, resolved_text[:80])

		await self._broadcast(
			message_text,
			"user",
			extra={"bucket_file_ids": bucket_file_ids} if bucket_file_ids else None,
		)

		if bucket_file_ids:
			max_batch_size = settings.BUCKET_MAX_BATCH_SIZE_MB * _BYTES_PER_MB
			total_size = await _sum_bucket_file_sizes(
				bucket_file_ids, self.chat_session
			)
			if total_size > max_batch_size:
				await self._broadcast(_MSG_BATCH_TOO_LARGE, "alert")
				return

		expertise_level = validated["expertise_level"]

		if await self.n8n_queue.try_start():
			asyncio.create_task(
				self._fire_n8n(
					resolved_text,
					bucket_file_ids=bucket_file_ids,
					expertise_level=expertise_level,
					language=language,
				)
			)
		else:
			# Another execution for this chat is already in flight — replace whatever
			# was previously queued (only the latest message survives) instead of
			# firing now. The n8n callback handler re-fires this once the in-flight
			# execution's result has been persisted. Org/user are captured here as
			# plain dicts because the callback runs in a separate request context
			# with no access to this connection's live auth/session object.
			organization_dict = await database_sync_to_async(
				self.organization.safe_to_dict
			)()
			await self.n8n_queue.set_pending(
				{
					"bucket_file_ids": bucket_file_ids,
					"expertise_level": expertise_level,
					"group_name": self.group_name,
					"language": language,
					"message": resolved_text,
					"organization": organization_dict,
					"session_id": self.chat_session.id if self.chat_session else None,
					"user": self.user.to_dict(),
				}
			)
			await self._broadcast(_MSG_QUEUED, "status")

	async def _fire_n8n(  # pylint: disable=too-many-arguments
		self,
		message_text,
		*,
		bucket_file_ids=None,
		expertise_level,
		language=None,
		max_retries=5,
		retry_delay=30,
	):
		"""Fire message to n8n webhook with retry on transient failures."""

		# Retries up to max_retries times with retry_delay seconds between attempts.
		# Broadcasts AGENT_UNAVAILABLE if all attempts fail.

		for attempt in range(max_retries):
			try:
				await self.n8n_client.fire(
					bucket_file_ids=bucket_file_ids,
					expertise_level=expertise_level,
					group_name=self.group_name,
					language=language,
					message=message_text,
					organization=self.organization,
					session_id=self.chat_session.id if self.chat_session else None,
					state=self.n8n_state,
					user=self.user,
				)
				return
			except N8nClientError:
				if attempt < max_retries - 1:
					await asyncio.sleep(retry_delay)
					continue
				# n8n never accepted the job, so no callback will ever arrive to
				# release the lock — release it now or this chat stays blocked
				# until the TTL expires.
				await self.n8n_queue.release()
				await self._broadcast(_MSG_AGENT_UNAVAILABLE, "alert")
				await self._fire_pending_if_any()
			except Exception:  # pylint: disable=broad-except
				await self.n8n_queue.release()
				await self._broadcast(_MSG_AGENT_ERROR, "alert")
				await self._fire_pending_if_any()
				return

	async def _fire_pending_if_any(self):
		"""Start a queued message left behind after this execution never started."""
		# Only relevant on the failure path above: the normal success path is handled
		# by the n8n callback once the in-flight execution's result comes back.
		pending = await self.n8n_queue.pop_pending()
		if not pending:
			return
		if await self.n8n_queue.try_start():
			asyncio.create_task(
				self._fire_n8n(
					pending["message"],
					bucket_file_ids=pending.get("bucket_file_ids") or [],
					expertise_level=pending["expertise_level"],
					language=pending.get("language"),
				)
			)
		else:
			# Lost the race to another execution starting in the meantime — put it
			# back rather than silently dropping it.
			await self.n8n_queue.set_pending(pending)

	async def set_processes(self, event):
		"""Channel layer handler: store pending processes for the next disambiguation reply."""
		self.pending_processes = event.get("processes")

	async def resolve_context(self):
		"""Resolve org/user details, initialise n8n helpers, and resume a DB session if requested."""

		# New sessions are created lazily on the first message to avoid empty orphan records.

		self.pending_processes = None
		self.organization = self.scope.get("organization")
		self.connection_key = ""
		if hasattr(self.user, "session") and self.user.session:
			self.connection_key = getattr(self.user.session, "connection_key", "")

		group_name = self.get_group_name()
		self.n8n_client = N8nClient()
		self.n8n_state = N8nSessionState(group_name=group_name)
		self.n8n_queue = N8nQueueState(group_name=group_name)

		self.chat_session = None

		if self._resume_session_id:
			self.chat_session = await _load_session(
				connection_key=self.connection_key,
				org_id=self.organization.id,
				session_id=self._resume_session_id,
				username=self.user.username,
			)
			if self.chat_session and self.chat_session.n8n_state:
				await self.n8n_state.restore(self.chat_session.n8n_state)
		else:
			await self.n8n_state.clear()

	async def websocket_disconnect(self, message):
		"""Clean up Redis connections on disconnect."""
		# Does not release the in-flight lock or clear anything pending — an execution
		# started before disconnect is still running server-side and will still call
		# back, and the lock's TTL is the safety net for the case where it doesn't.
		if self.n8n_state:
			await self.n8n_state.close()
		if self.n8n_queue:
			await self.n8n_queue.close()
		await super().websocket_disconnect(message)
