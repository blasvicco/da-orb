"""B1S authentication driver"""

# General imports
import time

# Lib imports
import requests
from django.utils import timezone

# App imports
from drf_api.models import MSession, MSessionProxy
from drf_api.resources.auth.driver.abstract import AAuthDriver, AuthDriverError

B1S_SESSION_TTL = 1800  # 30 minutes in seconds


class Instance(AAuthDriver):
	"""SAP Business One Service Layer authentication driver."""

	def __init__(self, integration: dict):
		"""Initialise the B1S driver."""
		super().__init__(integration)
		base_url = integration.get("base_url", "").rstrip("/")
		self._login_url = f"{base_url}/Login"

	def authenticate(self, **credentials) -> dict:
		"""Authenticate against SAP B1S and return a normalised session dict. Raises AuthDriverError on failure."""
		# Expected credentials: database (str), org (str), password (str), username (str)
		database = credentials.get("database", "")
		password = credentials.get("password", "")
		username = credentials.get("username", "")
		token = credentials.get("token", "")

		# WS middleware context: a B1S SessionId is not a JWT and can't be verified
		# cheaply. Trust the token here; credentials are validated in auth.init.
		if token and not password:
			session = MSession(
				access_token=token,
				database=database,
				expires_at=credentials.get("expires_at", 0)
				or int(time.time()) + B1S_SESSION_TTL,
				id_token="",
				refresh_token="",
				user={"password": "", "username": username},
			)
			return session.to_dict()

		if not database:
			raise AuthDriverError("MISSING_DATABASE", status_code=400)

		payload = {
			"CompanyDB": database,
			"Password": password,
			"UserName": username,
		}

		try:
			res = requests.post(
				self._login_url,
				json=payload,
				timeout=15,
				verify=False,
			)
		except requests.RequestException as error:
			raise AuthDriverError(str(error), status_code=502) from error

		if res.status_code != 200:
			try:
				response_data = res.json()
			except Exception:  # pylint: disable=broad-except
				response_data = {}
			error_msg = (
				response_data.get("error", {}).get("message", {}).get("value")
				or response_data.get("error")
				or "B1S_AUTH_FAILED"
			)
			raise AuthDriverError(
				error_msg, response_data=response_data, status_code=res.status_code
			)

		try:
			session_id = res.json().get("SessionId", "")
		except Exception as error:  # pylint: disable=broad-except
			raise AuthDriverError("B1S_INVALID_RESPONSE", status_code=502) from error

		session = MSession(
			access_token=session_id,
			database=database,
			expires_at=int(time.time()) + B1S_SESSION_TTL,
			id_token="",
			refresh_token="",
			user={
				"password": password,
				"username": username,
			},
		)
		return session.to_dict()

	def login(self, request, org: str):
		"""Process B1S login request; returns a normalised session dict. Raises AuthDriverError on failure."""
		database = request.data.get("database", "").strip()
		password = request.data.get("password", "")
		username = request.data.get("username", "").strip()

		if not username or not password or not database:
			raise AuthDriverError("MISSING_CREDENTIALS", status_code=400)

		return self.authenticate(
			database=database, password=password, username=username
		)

	def refresh(self, **token_data) -> dict:  # pylint: disable=unused-argument
		"""B1S does not support token refresh. Raises AuthDriverError."""
		raise AuthDriverError("B1S_REFRESH_NOT_SUPPORTED", status_code=400)

	def resolve_identity(self, request) -> tuple:
		"""Resolve identity from the verified opaque proxy token (MSessionProxy)."""
		# A B1S SessionId-derived token can't be trusted at face value, so identity
		# is looked up here rather than read from client-supplied headers.
		session = self.resolve_session(self.__extract_bearer_token(request))
		if session is None:
			return "", ""
		return session.username, session.connection_key

	@staticmethod
	def resolve_session(token: str):
		"""Look up an active B1S MSessionProxy row by its opaque token, refreshing last_active_on. Returns None if missing/expired."""
		if not token:
			return None
		try:
			session = MSessionProxy.objects.select_related("org").get(
				auth_driver="b1s",
				expires_at__gt=timezone.now(),
				token=token,
			)
		except MSessionProxy.DoesNotExist:
			return None
		MSessionProxy.objects.filter(pk=session.pk).update(
			last_active_on=timezone.now()
		)
		return session

	def resolve_session_payload(self, session_dict: dict) -> dict:
		"""Swap in the real B1S credentials at fire time."""
		# The live session only ever holds an opaque proxy token, never the raw password.
		session = self.resolve_session(session_dict.get("access_token", ""))
		if session is None:
			return session_dict
		return {
			**session_dict,
			"database": session.connection_key,
			"user": {
				"password": session.credentials.get("password", ""),
				"username": session.credentials.get("username", ""),
			},
		}

	# pylint: disable-next=unused-argument
	def resolve_ws_session(self, session_data: dict, *, org: str, token: str, username: str = None) -> dict:
		"""Resolve a WebSocket reconnect session from the verified opaque proxy token, or None if it can't be resolved."""
		# The proxy token is verified against MSessionProxy rather than trusting the
		# client-supplied org/username, which B1S's opaque SessionId can't vouch for itself.
		session = self.resolve_session(token)
		if session is None:
			return None
		return MSession(
			access_token=token,
			database=session.connection_key,
			expires_at=session_data.get("expires_at", 0),
			id_token="",
			refresh_token="",
			user={"password": "", "username": session.username},
		).to_dict()

	@staticmethod
	def __extract_bearer_token(request) -> str:
		"""Return the raw token from an 'Authorization: Bearer <token>' header, or empty string."""
		auth = request.headers.get("Authorization", "")
		return auth[7:] if auth.startswith("Bearer ") else ""
