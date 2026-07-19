"""Open ID Connect authentication driver"""

# General imports
import time

# App imports
from drf_api.models import MSession
from drf_api.resources.auth.driver.abstract import AAuthDriver, AuthDriverError
from drf_api.resources.auth.helpers import SapOAuthClient, SapOAuthError


class Instance(AAuthDriver):
	"""SAP XSUAA Open ID Connect authentication driver."""

	def __init__(self, integration: dict):
		"""Initialise the Open ID driver."""
		super().__init__(integration)
		self._client = SapOAuthClient(integration)

	def authenticate(self, **credentials) -> dict:
		"""Exchange an authorisation code for tokens. Raises AuthDriverError on failure."""
		# Expected credentials: code (str), org (str), redirect_uri (str)
		code = credentials.get("code")
		org = credentials.get("org", "")
		redirect_uri = credentials.get("redirect_uri")

		try:
			token_data = self._client.exchange_code(
				code=code, redirect_uri=redirect_uri
			)
		except SapOAuthError as error:
			raise AuthDriverError(
				str(error),
				response_data=error.response_data,
				status_code=error.status_code,
			) from error

		return self._build_session(token_data, org=org)

	def login(self, request, org: str):
		"""Open ID does not support credential-based login. Raises AuthDriverError."""
		raise AuthDriverError("METHOD_NOT_ALLOWED", status_code=405)

	def refresh(self, **token_data) -> dict:
		"""Exchange a refresh token for a new token set. Raises AuthDriverError on failure."""
		# Expected token_data: org (str), refresh_token (str)
		org = token_data.get("org", "")
		refresh_token = token_data.get("refresh_token")

		try:
			new_token_data = self._client.refresh_token(refresh_token)
		except SapOAuthError as error:
			raise AuthDriverError(
				str(error),
				response_data=error.response_data,
				status_code=error.status_code,
			) from error

		return self._build_session(
			new_token_data,
			org=org,
			fallback_refresh=refresh_token,
		)

	# pylint: disable-next=useless-parent-delegation
	def resolve_identity(self, request) -> tuple:
		"""Resolve identity from the X-SAP-Username/X-SAP-Connection-Key headers."""
		# Open ID has no opaque-token concept to verify against, so it keeps the base
		# class's header-trust default — redeclared here so every driver's full
		# capability set is visible from its own file, not just the abstract base.
		return super().resolve_identity(request)

	# pylint: disable-next=useless-parent-delegation
	def resolve_session_payload(self, session_dict: dict) -> dict:
		"""Pass the session dict through unchanged."""
		# Open ID sessions already carry a real OAuth access token, so there is
		# nothing to swap in at fire time — this keeps the base class default,
		# redeclared here for the same visibility reason as resolve_identity above.
		return super().resolve_session_payload(session_dict)

	def _build_session(
		self,
		token_data: dict,
		*,
		fallback_refresh: str = "",
		org: str = "",
	) -> dict:
		"""Build a normalised session dict from a raw XSUAA token response."""
		id_token = token_data.get("id_token", "")
		user_info = {}
		if id_token:
			payload = SapOAuthClient.decode_jwt_payload(id_token)
			user_info = SapOAuthClient.extract_user_info(payload)

		session = MSession(
			access_token=token_data.get("access_token"),
			expires_at=int(time.time()) + int(token_data.get("expires_in", 3600)),
			id_token=id_token,
			org=org,
			refresh_token=token_data.get("refresh_token") or fallback_refresh,
			user=user_info,
		)
		return session.to_dict()
