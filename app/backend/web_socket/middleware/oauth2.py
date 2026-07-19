"""OAuth2 Middleware"""

# General imports
import time
from urllib.parse import parse_qs

# Libs imports
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

# App imports
from drf_api.models import MOrganization, MSession
from drf_api.resources.auth.factory import FAuthenticator
from drf_api.resources.auth.helpers import SapOAuthClient, has_active_seat


@database_sync_to_async
def get_org_and_user(org_slug, session_data, token, username=None):
	"""Get organization and user info from slug/token."""
	# session_data: dict with keys expires_at, database, password

	class WsUser:  # pylint: disable=too-few-public-methods
		"""Mock user class for authenticated WebSocket users."""

		is_authenticated = True
		session = None

		def __init__(self, session=None):
			"""Initialise the user."""
			self.session = session

		@property
		def username(self) -> str:
			"""Get username from session user dictionary."""
			return self.session.user.get("username", "") if self.session else ""

		def to_dict(self):
			"""Convert to dictionary."""
			return self.session.to_dict()

	org, _error = MOrganization.get_by_slug(org_slug)
	if org is None:
		return None, AnonymousUser()

	if not token:
		return org, AnonymousUser()

	try:
		driver = FAuthenticator.get_instance(
			driver=org.integration.get("auth_driver", "open_id"),
			integration=org.integration,
		)
	except Exception:  # pylint: disable=broad-except
		return org, AnonymousUser()

	session_dict = driver.resolve_ws_session(
		session_data,
		org=org_slug,
		token=token,
		username=username
	)
	if session_dict is None:
		return org, AnonymousUser()

	resolved_username = session_dict.get("user", {}).get("username", "")
	if not has_active_seat(org, resolved_username):
		return org, AnonymousUser()

	return org, WsUser(session=MSession(**session_dict))


class MOAuth2:  # pylint: disable=too-few-public-methods
	"""Middleware for OAuth2 on Web Socket."""

	def __init__(self, inner):
		"""Constructor."""
		self.inner = inner

	async def __call__(self, scope, receive, send):
		"""Call method."""
		query_string = scope.get("query_string", b"").decode()
		params = parse_qs(query_string)
		token = params.get("token", [None])[0]
		username = params.get("username", [None])[0]

		# password travels in the WS query-string — MUST use WSS (TLS) in production.
		database = params.get("database", [""])[0]
		password = params.get("password", [""])[0]

		# Decode the JWT expiry claim so n8n has full session context.
		expires_at = 0
		if token:
			jwt_payload = SapOAuthClient.decode_jwt_payload(token)
			exp = jwt_payload.get("exp")
			expires_at = int(exp) if exp else int(time.time()) + 1800

		# Extract org_slug from request host subdomain.
		headers = dict(scope.get("headers", []))
		host = headers.get(b"host", b"").decode("utf-8")
		org_slug = host.split(".")[0] if host else None

		scope["organization"] = None
		scope["user"] = AnonymousUser()

		if org_slug and token:
			session_data = {
				"expires_at": expires_at,
				"database": database,
				"password": password,
			}
			org, user = await get_org_and_user(
				org_slug,
				session_data,
				token,
				username=username,
			)
			scope["organization"] = org
			scope["user"] = user

		return await self.inner(scope, receive, send)
