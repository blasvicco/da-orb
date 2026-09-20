"""DRF auth viewset"""

# General imports
import base64
import json
import urllib.parse

# Lib imports
from django.shortcuts import redirect
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

# App imports
from core.modules.hooks import Hooks
from drf_api.models import MOrganization, MSessionProxy
from drf_api.resources.auth.driver.abstract import AuthDriverError
from drf_api.resources.auth.helpers import is_org_admin
from drf_api.resources.auth.permission import PAuth
from drf_api.validators import VAuthenticatorExist

USER_AUTHENTICATED = "user_authenticated"


def _notify_user_authenticated(org, username):
	"""Announce a successful authentication so other domains can react, without auth needing to import or know about them."""
	# A listener may raise to abort the flow; it propagates straight back to the caller.
	for method, _, _ in Hooks.get_listeners(USER_AUTHENTICATED):
		method(org, username)


class VSAuth(viewsets.ViewSet):
	"""Auth View Set"""

	# Public endpoints — no session auth, so SessionAuthentication's CSRF
	# enforcement is bypassed. CSRF protection is irrelevant here because
	# these routes are not session-cookie-based.
	authentication_classes = []
	permission_classes = [PAuth]

	@action(detail=False, methods=["get", "post"])
	# pylint: disable=too-many-locals
	def callback(self, request, *args, **kwargs):
		"""Callback for the Open ID (OAuth) auth flow."""
		host = request.get_host()
		port = str(request.get_port() or "")
		port = "" if port in ("80", "443", "") else ":" + port
		frontend_base = f"{request.scheme}://{host}{port}"

		sap_error = request.query_params.get(
			"error_description"
		) or request.query_params.get("error")
		if sap_error:
			return redirect(f"{frontend_base}/?error={urllib.parse.quote(sap_error)}")

		code = request.query_params.get("code")
		if not code:
			return redirect(f"{frontend_base}/?error=AUTHORIZATION_MISSING_CODE")

		slug = request.get_org_slug()
		org, error_redirect = MOrganization.get_by_slug(slug, frontend_base)
		if error_redirect:
			return redirect(error_redirect)

		try:
			driver = VAuthenticatorExist()(
				driver=org.integration.get("auth_driver", "open_id"),
				integration=org.integration,
			)
			session_data = driver.authenticate(
				code=code,
				org=slug,
				redirect_uri=request.build_absolute_uri(request.path),
			)
		except (AuthDriverError, ValueError, ValidationError) as error:
			error_msg = error.detail if hasattr(error, "detail") else str(error)
			if isinstance(error_msg, list) and len(error_msg) > 0:
				error_msg = error_msg[0]
			return redirect(
				f"{frontend_base}/?error={urllib.parse.quote(str(error_msg))}"
			)

		username = session_data.get("user", {}).get("username", "")
		try:
			_notify_user_authenticated(org, username)
		except ValidationError as error:
			error_msg = error.detail if hasattr(error, "detail") else str(error)
			if isinstance(error_msg, list) and len(error_msg) > 0:
				error_msg = error_msg[0]
			return redirect(
				f"{frontend_base}/?error={urllib.parse.quote(str(error_msg))}"
			)
		session_data["role"] = "admin" if is_org_admin(org, username) else "standard"

		session_b64 = base64.b64encode(json.dumps(session_data).encode()).decode()
		return redirect(f"{frontend_base}/auth/callback?session={session_b64}")

	@action(detail=False, methods=["post"])
	def login(self, request, *args, **kwargs):
		"""Credential-based login. POST body requirements depend on the driver."""
		slug = request.get_org_slug()
		org, _ = MOrganization.get_by_slug(slug)
		if org is None:
			return Response({"error": "ORGANIZATION_NOT_FOUND"}, status=404)

		try:
			driver = VAuthenticatorExist()(
				driver=org.integration.get("auth_driver", "open_id"),
				integration=org.integration,
			)
			session_data = driver.login(request, org=slug)
		except AuthDriverError as error:
			return Response({"error": str(error)}, status=error.status_code or 401)
		except (ValidationError, ValueError) as error:
			error_msg = error.detail if hasattr(error, "detail") else str(error)
			return Response({"error": error_msg}, status=400)

		if org.integration.get("auth_driver") == "b1s":
			username = session_data["user"]["username"]
			try:
				_notify_user_authenticated(org, username)
			except ValidationError as error:
				error_msg = error.detail if hasattr(error, "detail") else str(error)
				if isinstance(error_msg, list) and len(error_msg) > 0:
					error_msg = error_msg[0]
				return Response({"error": error_msg}, status=403)

			# The browser must never see the raw password again after this point — the
			# opaque token below is all it gets; credentials stay encrypted server-side
			# and are only decrypted again when a message is actually fired to n8n.
			session_proxy = MSessionProxy.issue(
				auth_driver="b1s",
				connection_key=session_data["database"],
				org=org,
				password=session_data["user"]["password"],
				username=username,
			)
			session_data["access_token"] = session_proxy.token
			session_data["user"]["password"] = ""
			session_data["role"] = (
				"admin" if is_org_admin(org, username) else "standard"
			)

		return Response(session_data)

	@action(detail=False, methods=["post"])
	def refresh(self, request, *args, **kwargs):
		"""Refresh the SAP integration token (open_id only)."""
		refresh_token = request.data.get("token")
		if not refresh_token:
			return Response({"error": "Missing refresh_token."}, status=400)

		slug = request.get_org_slug()
		org, _ = MOrganization.get_by_slug(slug)
		if org is None:
			return Response({"error": "ORGANIZATION_NOT_FOUND"}, status=404)

		try:
			driver = VAuthenticatorExist()(
				driver=org.integration.get("auth_driver", "open_id"),
				integration=org.integration,
			)
			session_data = driver.refresh(org=slug, refresh_token=refresh_token)
		except AuthDriverError as error:
			return Response(
				error.response_data or {"error": str(error)},
				status=error.status_code or 502,
			)
		except (ValueError, ValidationError) as error:
			error_msg = error.detail if hasattr(error, "detail") else str(error)
			return Response({"error": error_msg}, status=400)

		username = session_data.get("user", {}).get("username", "")
		session_data["role"] = "admin" if is_org_admin(org, username) else "standard"

		return Response(session_data)
