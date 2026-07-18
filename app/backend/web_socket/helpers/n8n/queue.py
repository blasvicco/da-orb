"""n8n In-Flight Queue — Redis-backed per-chat serialization for n8n executions"""

# General imports
import json
import logging

# Libs imports
from django.conf import settings
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_INFLIGHT_KEY_PREFIX = "n8n:inflight"
_PENDING_KEY_PREFIX = "n8n:pending"


class N8nQueueState:
	"""Redis-backed per-chat in-flight guard with a single-slot pending queue.

	Firing a message to n8n no longer waits for the workflow to finish, so nothing
	stops a chat from having more than one execution in flight at once if the user
	sends again before the first reply arrives. Since every execution for a chat
	reads and writes the same N8nSessionState bucket, concurrent executions race
	and corrupt each other's state. This guard ensures at most one execution is in
	flight per chat: a message that arrives while one is already running doesn't
	fire immediately — it replaces whatever was previously pending (only the latest
	superseded message is kept, not a full history) and fires once the in-flight
	execution's result has been persisted.
	"""

	def __init__(self, group_name: str):
		"""Initialise the queue state for one chat (group_name already scopes it per chat)."""
		self._inflight_key = f"{_INFLIGHT_KEY_PREFIX}:{group_name}"
		self._pending_key = f"{_PENDING_KEY_PREFIX}:{group_name}"
		self._redis = Redis(
			decode_responses=True,
			host=settings.CONFIG.get("REDIS_HOST", "localhost"),
			port=int(settings.CONFIG.get("REDIS_PORT", 6379)),
			socket_connect_timeout=5,
			socket_timeout=5,
		)
		# Safety net so a crash between try_start() and the matching callback can't
		# wedge a chat permanently — the lock expires and a later message can proceed.
		self._ttl = settings.CONFIG.get("N8N_INFLIGHT_TTL_SECONDS", 300)

	async def try_start(self) -> bool:
		"""Attempt to acquire the in-flight lock for this chat.

		Returns True if acquired (caller should fire to n8n now), False if another
		execution is already in flight (caller should queue instead).
		"""
		try:
			acquired = await self._redis.set(
				self._inflight_key, "1", nx=True, ex=self._ttl
			)
			return bool(acquired)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nQueueState: failed to acquire in-flight lock for %s",
				self._inflight_key,
			)
			# Fail open — a Redis outage shouldn't silently swallow the user's message.
			return True

	async def release(self) -> None:
		"""Release the in-flight lock (called once the execution's result is back)."""
		try:
			await self._redis.delete(self._inflight_key)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nQueueState: failed to release in-flight lock for %s",
				self._inflight_key,
			)

	async def set_pending(self, payload: dict) -> None:
		"""Store (overwriting any previous) pending message to fire once the current one completes."""
		try:
			await self._redis.set(self._pending_key, json.dumps(payload), ex=self._ttl)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nQueueState: failed to set pending message for %s", self._pending_key
			)

	async def pop_pending(self) -> dict | None:
		"""Return and clear the pending message, if any."""
		try:
			raw = await self._redis.get(self._pending_key)
			if not raw:
				return None
			await self._redis.delete(self._pending_key)
			return json.loads(raw)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nQueueState: failed to pop pending message for %s", self._pending_key
			)
			return None

	async def close(self) -> None:
		"""Close the underlying Redis connection pool."""
		try:
			await self._redis.aclose()
		except Exception:  # pylint: disable=broad-except
			logger.exception("N8nQueueState: failed to close Redis connection")
