"""B1S authentication driver"""

# General imports
import time

# Lib imports
import requests
from rest_framework.response import Response

# App imports
from drf_api.models import MSession
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
		database = credentials.get("database") or self._integration.get(
			"database",
			"",
		)
		password = credentials.get("password", "")
		username = credentials.get("username", "")
		token = credentials.get("token", "")

		# WS middleware context: a B1S SessionId is not a JWT and can't be verified
		# cheaply. Trust the token here; credentials are validated in auth.init.
		if token and not password:
			session = MSession(
				access_token=token,
				database=database,
				expires_at=credentials.get("expires_at", 0) or int(time.time()) + B1S_SESSION_TTL,
				id_token="",
				refresh_token="",
				user={"password": "", "username": username},
			)
			return session.to_dict()

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
		"""Process B1S login request."""
		password = request.data.get("password", "")
		username = request.data.get("username", "").strip()

		if not username or not password:
			return Response({"error": "MISSING_CREDENTIALS"}, status=400)

		try:
			session_data = self.authenticate(
				database=request.data.get("database", "").strip(),
				password=password,
				username=username,
			)
		except AuthDriverError as error:
			return Response({"error": str(error)}, status=error.status_code or 401)
		except ValueError as error:
			return Response({"error": str(error)}, status=400)

		return Response(session_data)

	def refresh(self, **token_data) -> dict:  # pylint: disable=unused-argument
		"""B1S does not support token refresh. Raises AuthDriverError."""
		raise AuthDriverError("B1S_REFRESH_NOT_SUPPORTED", status_code=400)

