"""n8n Session State — Redis-backed state machine for CChat sessions"""

# General imports
import json
import logging

# Libs imports
from django.conf import settings
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_STATE_KEY_PREFIX = "n8n:session"


class N8nSessionState:
	"""Redis-backed state machine for a single CChat WebSocket session."""

	# Redis key schema: n8n:session:<group_name>
	# Value: JSON { active_node_id, intention_nodes, last_bot_message } -- intention_nodes
	# is keyed by each node's own id (Record<id, Node>), the single source of truth for a
	# node's process_id/process_definition/form_state; no separate root-level copy.
	# TTL: FORM_STATE_TTL_SECONDS (default 86400 s = 24 h)

	def __init__(self, group_name: str):
		"""Initialise the state machine."""
		self._key = f"{_STATE_KEY_PREFIX}:{group_name}"
		self._redis = Redis(
			decode_responses=True,
			host=settings.REDIS_HOST,
			port=settings.REDIS_PORT,
			socket_connect_timeout=5,
			socket_timeout=5,
		)
		self._ttl = settings.FORM_STATE_TTL_SECONDS

	async def clear(self) -> None:
		"""Delete the state key from Redis (used on disconnect or unrecoverable error)."""
		try:
			await self._redis.delete(self._key)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nSessionState: failed to clear state for key %s", self._key
			)

	async def close(self) -> None:
		"""Close the underlying Redis connection pool."""
		try:
			await self._redis.aclose()
		except Exception:  # pylint: disable=broad-except
			logger.exception("N8nSessionState: failed to close Redis connection")

	async def load(self) -> dict:
		"""Return the current state dict from Redis (empty dict if not set)."""
		try:
			raw = await self._redis.get(self._key)
			if raw:
				return json.loads(raw)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nSessionState: failed to load state for key %s", self._key
			)
		return {}

	async def restore(self, state: dict) -> None:
		"""Write a saved state dict directly to Redis (used when resuming a session)."""
		try:
			await self._redis.set(self._key, json.dumps(state), ex=self._ttl)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nSessionState: failed to restore state for key %s", self._key
			)

	async def save(
		self,
		*,
		active_node_id=None,
		intention_nodes=None,
		last_bot_message=None,
	) -> None:
		"""Persist state to Redis, refreshing the TTL."""
		state = {
			"active_node_id": active_node_id,
			"intention_nodes": intention_nodes or {},
			"last_bot_message": last_bot_message,
		}
		try:
			await self._redis.set(self._key, json.dumps(state), ex=self._ttl)
		except Exception:  # pylint: disable=broad-except
			logger.exception(
				"N8nSessionState: failed to save state for key %s", self._key
			)
