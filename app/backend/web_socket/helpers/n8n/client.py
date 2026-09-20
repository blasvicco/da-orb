"""n8n Client — async HTTP wrapper for the n8n chat webhook"""

# General imports
import logging

# Libs imports
import httpx
from channels.db import database_sync_to_async

# App imports
from drf_api.resources.auth.factory import FAuthenticator

logger = logging.getLogger(__name__)


class N8nClientError(Exception):
	"""Raised when the n8n webhook returns a non-2xx response."""

	def __init__(self, message, response_data=None, status_code=None):
		"""Initialise the error."""
		super().__init__(message)
		self.response_data = response_data or {}
		self.status_code = status_code


class N8nWebhookNotReadyError(N8nClientError):
	"""Raised when the n8n webhook is not yet registered (HTTP 404)."""


class N8nClient:  # pylint: disable=too-few-public-methods
	"""Async HTTP wrapper around the n8n chat webhook."""

	def __init__(self, timeout: int = 60):
		"""Initialise the client."""
		self._timeout = timeout
		# self._webhook_url = settings.CONFIG.get('N8N_CHAT_WEBHOOK_URL')
		self._webhook_url = "http://n8n.blas.local:5678/webhook/chat"

	async def fire(  # pylint: disable=too-many-arguments,too-many-locals
		self,
		*,
		bucket_file_ids=None,
		expertise_level: int,
		group_name: str,
		language: str,
		message: str,
		organization,
		session_id,
		state,
		user,
	) -> None:
		"""POST a chat message to the n8n webhook (fire-and-forget)."""

		# Sends the message and current session state to n8n; does not wait for a
		# result payload. n8n is responsible for calling back via the n8n_callback
		# REST endpoint when the workflow finishes.
		# Raises N8nClientError on connection failure or non-2xx response.

		current = await state.load()
		organization_dict = await database_sync_to_async(organization.safe_to_dict)()
		session_payload = await self._resolve_session_payload(organization_dict, user)

		payload = {
			"active_node_id": current.get("active_node_id"),
			# References only — the Agent resolves each bucket file's content on demand
			# via its own extraction tool rather than the platform embedding it here.
			"bucket_file_ids": bucket_file_ids or [],
			"expertise_level": expertise_level,
			"group_name": group_name,
			"intention_nodes": current.get("intention_nodes") or {},
			"language": language,
			"message": message,
			# Only integration/slug are read by any v14 workflow node (SAP connection
			# setup, GitHub schema lookups) — name/plan/seat_limit/created_on/id are
			# never referenced, so they're dropped rather than round-tripped forever
			# through every intention_nodes[id] copy stored in n8n_state.
			"organization": {
				"integration": organization_dict.get("integration"),
				"slug": organization_dict.get("slug"),
			},
			# Only access_token/database/user are read by any v14 workflow node —
			# expires_at/id_token/org/refresh_token are never referenced.
			"session": {
				"access_token": session_payload.get("access_token"),
				"database": session_payload.get("database"),
				"user": session_payload.get("user"),
			},
			"session_id": session_id,
		}
		# Only include last_bot_message when set — grounds Agent: Form on what it
		# just asked, without ever growing beyond a single prior message.
		if current.get("last_bot_message"):
			payload["last_bot_message"] = current.get("last_bot_message")

		logger.debug(
			"N8nClient: firing to %s group=%s active_node_id=%s",
			self._webhook_url,
			group_name,
			current.get("active_node_id"),
		)
		try:
			# verify=False because the SAP B1 target uses a self-signed certificate.
			# This flag is intentionally scoped to this client only.
			async with httpx.AsyncClient(timeout=self._timeout, verify=False) as http:
				resp = await http.post(self._webhook_url, json=payload)
		except httpx.RequestError as exc:
			raise N8nClientError(str(exc)) from exc

		if resp.status_code == 404:
			raise N8nWebhookNotReadyError(
				"n8n webhook is not yet registered",
				status_code=404,
			)

		if resp.status_code >= 400:
			raise N8nClientError(
				f"n8n webhook returned {resp.status_code}",
				status_code=resp.status_code,
			)

	async def _resolve_session_payload(self, organization_dict, user):
		"""Return the session dict to send to n8n, resolved through the org's auth driver."""
		# B1S swaps in decrypted credentials at fire time; other drivers pass the session
		# through unchanged. The driver is detected from org settings via FAuthenticator.
		integration = organization_dict.get("integration", {})
		driver = FAuthenticator.get_instance(
			driver=integration.get("auth_driver", "open_id"),
			integration=integration,
		)
		return await database_sync_to_async(driver.resolve_session_payload)(
			user.to_dict()
		)
