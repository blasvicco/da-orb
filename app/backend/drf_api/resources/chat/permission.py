"""Chat permission"""

# Lib imports
from django.conf import settings

# App imports
from drf_api.resources import BasePermission
from drf_api.resources.auth.helpers import has_active_seat


class PChat(BasePermission):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	# Real SAP session validation happens at the WS layer.

	def has_permission(self, request, view):
		"""Return True if the request carries a non-empty Bearer token and an active seat."""
		auth = request.headers.get("Authorization", "")
		if not (auth.startswith("Bearer ") and bool(auth[7:])):
			return False
		org, username, _ = view._get_org_and_user(  # pylint: disable=protected-access
			request
		)
		if org is None or not username:
			return False
		return has_active_seat(org, username)

	def has_object_permission(self, request, view, obj):
		"""Allow destructive operations only when the requester owns the object."""
		# Ownership is resolved via view._get_org_and_user() rather than reading headers
		# directly, so B1S orgs get the same verified-token identity check used for the
		# read endpoints — a raw X-SAP-Username header can no longer be spoofed here.
		if request.method in ("DELETE", "PUT", "PATCH"):
			(
				_,
				username,
				connection_key,
			) = view._get_org_and_user(  # pylint: disable=protected-access
				request
			)
			return (
				bool(username)
				and obj.username == username
				and obj.connection_key == connection_key
			)
		return True


class PN8nCallback(BasePermission):
	"""Require the correct shared secret in X-N8n-Secret header (server-to-server only)."""

	def has_permission(self, request, view):
		"""Return True if the request carries the configured n8n callback secret."""
		secret = getattr(settings, "N8N_CALLBACK_SECRET", "")
		return bool(secret) and request.headers.get("X-N8n-Secret") == secret
