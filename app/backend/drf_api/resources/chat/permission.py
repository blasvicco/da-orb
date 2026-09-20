"""Chat permission"""

# Lib imports
from django.conf import settings

# App imports
from drf_api.resources import BasePermission, PHasActiveSeat
from drf_api.resources.auth.helpers import resolve_request_identity


class PChat(PHasActiveSeat):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	# Real SAP session validation happens at the WS layer.

	def has_object_permission(self, request, view, obj):
		"""Allow destructive operations only when the requester owns the object."""
		# Resolved via resolve_request_identity() rather than trusted directly from
		# request headers, so B1S orgs get the same verified-token identity check
		# used for the read endpoints — a raw X-SAP-Username header can no longer be
		# spoofed here.
		if request.method in ("DELETE", "PUT", "PATCH"):
			_, username, connection_key = resolve_request_identity(request)
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
