"""Auth driver base"""

# General imports
from abc import ABC, abstractmethod


class AuthDriverError(Exception):
	"""Raised when an auth driver fails to authenticate or refresh."""

	def __init__(self, message, response_data=None, status_code=None):
		"""Initialize AuthDriverError."""
		super().__init__(message)
		self.response_data = response_data or {}
		self.status_code = status_code


class AAuthDriver(ABC):
	"""Abstract SAP authentication driver — all drivers must implement authenticate() and refresh()."""

	# authenticate(), login(), and refresh() all return a normalised session dict:
	# {
	#   "access_token":  str,
	#   "expires_at":    int,  # Unix timestamp
	#   "id_token":      str,  # empty when N/A
	#   "org":           str,  # organisation slug
	#   "refresh_token": str,  # empty when N/A
	#   "user": { "email": str, "first_name": str, "last_name": str, "name": str, "username": str }
	# }

	def __init__(self, integration: dict):
		"""Initialise the driver with the organisation integration config."""
		self._integration = integration

	@abstractmethod
	def authenticate(self, **credentials) -> dict:
		"""Validate credentials and return a normalised session dict. Raises AuthDriverError on failure."""

	@abstractmethod
	def login(self, request, org: str):
		"""Process login request and return a normalised session dict. Raises AuthDriverError on failure."""

	@abstractmethod
	def refresh(self, **token_data) -> dict:
		"""Refresh an existing session and return an updated session dict. Raises AuthDriverError on failure."""

	def resolve_identity(self, request) -> tuple:
		"""Return (username, connection_key) for this request."""
		# Default: trust the
		# X-SAP-Username/X-SAP-Connection-Key headers. Drivers whose client-supplied
		# token can't be trusted at face value (e.g. B1S's opaque proxy token) should
		# override this with a verified lookup instead.
		return (
			request.headers.get("X-SAP-Username", ""),
			request.headers.get("X-SAP-Connection-Key", ""),
		)

	def resolve_session_payload(self, session_dict: dict) -> dict:
		"""Return the session dict to hand off to n8n."""
		# Default: pass it through unchanged.
		# Drivers whose live session only carries an opaque token (e.g. B1S) should override
		# this to swap in the real credentials at fire time.
		return session_dict

	def resolve_ws_session(self, session_data: dict, *, org: str, token: str, username: str = None) -> dict:
		"""Resolve a WebSocket reconnect session dict, or None if it can't be resolved."""
		# Default: re-run authenticate() with the reconnect fields it already accepts.
		# Drivers whose live session only carries an opaque token (e.g. B1S) should override
		# this to verify it against their own persisted state instead.
		try:
			return self.authenticate(
				database=session_data.get("database", ""),
				expires_at=session_data.get("expires_at", 0),
				org=org,
				password=session_data.get("password", ""),
				token=token,
				username=username,
			)
		except Exception:  # pylint: disable=broad-except
			return None
