"""SAP OAuth2 client helper."""

# General imports
import base64
import json

# Lib imports
import requests


class SapOAuthError(Exception):
	"""Raised when the SAP token endpoint returns a non-200 response."""

	def __init__(self, message, response_data=None, status_code=None):
		"""Initialize the SAP OAuth error."""
		super().__init__(message)
		self.response_data = response_data or {}
		self.status_code = status_code


class SapOAuthClient:
	"""Thin wrapper around the SAP XSUAA OAuth2 token endpoint."""

	def __init__(self, integration: dict):
		"""Initialize the SAP OAuth2 client."""
		self.__client_id = integration.get("client_id")
		self.__client_secret = integration.get("client_secret")
		base_url = integration.get("base_url", "")
		self.__token_endpoint = (
			integration.get("token_endpoint")
			or f"{base_url.rstrip('/')}/oauth/token"
		)

	@staticmethod
	def decode_jwt_payload(token: str) -> dict:
		"""Decode a JWT payload without signature verification."""
		try:
			parts = token.split(".")
			if len(parts) >= 2:
				payload_b64 = parts[1]
				payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
				payload_bytes = base64.urlsafe_b64decode(payload_b64)
				return json.loads(payload_bytes.decode("utf-8"))
		except Exception:  # pylint: disable=broad-except
			pass
		return {}

	def exchange_code(self, code: str, redirect_uri: str) -> dict:
		"""Exchange an authorization code for tokens."""
		# Args:
		#   code: The authorization code received from the SAP callback.
		#   redirect_uri: Must match the URI used during the authorization request.
		data = {
			"client_id": self.__client_id,
			"client_secret": self.__client_secret,
			"code": code,
			"grant_type": "authorization_code",
			"redirect_uri": redirect_uri,
		}
		return self.__post_token(data)

	@staticmethod
	def extract_user_info(payload: dict) -> dict:
		"""Build a normalised user-info dict from a decoded JWT payload."""
		return {
			"email": payload.get("email", ""),
			"first_name": payload.get("given_name", ""),
			"last_name": payload.get("family_name", ""),
			"name": payload.get("name", ""),
			"username": payload.get("user_name") or payload.get("sub", ""),
		}

	def refresh_token(self, refresh_token: str) -> dict:
		"""Exchange a refresh token for a new token set."""
		data = {
			"client_id": self.__client_id,
			"client_secret": self.__client_secret,
			"grant_type": "refresh_token",
			"refresh_token": refresh_token,
		}
		return self.__post_token(data)

	def __post_token(self, data: dict) -> dict:
		"""POST to the token endpoint and return the parsed response."""
		try:
			res = requests.post(self.__token_endpoint, data=data, timeout=10)
		except requests.RequestException as error:
			raise SapOAuthError(str(error), status_code=502) from error

		if res.status_code != 200:
			try:
				response_data = res.json()
			except Exception:  # pylint: disable=broad-except
				response_data = {}
			error_msg = (
				response_data.get("error_description")
				or response_data.get("error")
				or "auth_failed"
			)
			raise SapOAuthError(
				error_msg, response_data=response_data, status_code=res.status_code
			)

		return res.json()
