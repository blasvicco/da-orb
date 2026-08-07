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
		active_node_override=None,
		bucket_file_ids=None,
		expertise_level: int = 2,
		group_name: str,
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
			# One-shot signal set only on the turn right after the user clicks a
			# tree node in the Intention Graph — distinct from the persisted
			# parent_override_id below, which survives turns where the workflow
			# needs a clarifying follow-up before actually creating the new node.
			"active_node_override": active_node_override,
			"awaiting_batch_confirmation": current.get(
				"awaiting_batch_confirmation", False
			),
			"awaiting_stack_resume": current.get("awaiting_stack_resume", False),
			# References only — the Agent resolves each bucket file's content on demand
			# via its own extraction tool rather than the platform embedding it here.
			"bucket_file_ids": bucket_file_ids or [],
			"expertise_level": expertise_level,
			"form_state": current.get("form_state"),
			"group_name": group_name,
			"intention_nodes": current.get("intention_nodes") or [],
			"message": message,
			"organization": organization_dict,
			"parent_override_id": current.get("parent_override_id"),
			"paused_node_ids": current.get("paused_node_ids") or [],
			"pending_batch_items": current.get("pending_batch_items") or [],
			"pending_processes": current.get("pending_processes"),
			"process_id": current.get("process_id"),
			"process_stack": current.get("process_stack") or [],
			"session": session_payload,
			"session_id": session_id,
		}
		# Only include last_bot_message when set — grounds Agent: Form on what it
		# just asked, without ever growing beyond a single prior message.
		if current.get("last_bot_message"):
			payload["last_bot_message"] = current.get("last_bot_message")
		# Only include process_definition when non-null to avoid polluting
		# the AI agent context with a null field on the first message.
		if current.get("process_definition") is not None:
			payload["process_definition"] = current.get("process_definition")

		logger.debug(
			"N8nClient: firing to %s group=%s process_id=%s",
			self._webhook_url,
			group_name,
			current.get("process_id"),
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
