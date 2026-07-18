"""Chat permission"""

# Lib imports
from django.conf import settings

# App imports
from drf_api.resources import BasePermission


class PChat(BasePermission):
	"""Require a non-empty Bearer token. Real SAP session validation happens at the WS layer."""

	def has_permission(self, request, view):
		"""Return True if the request carries a non-empty Bearer token."""
		auth = request.headers.get("Authorization", "")
		return auth.startswith("Bearer ") and bool(auth[7:])

	def has_object_permission(self, request, view, obj):
		"""Allow destructive operations only when the requester owns the object."""
		if request.method in ("DELETE", "PUT", "PATCH"):
			username = request.headers.get("X-SAP-Username", "")
			return bool(username) and obj.username == username
		return True


class PN8nCallback(BasePermission):
	"""Require the correct shared secret in X-N8n-Secret header (server-to-server only)."""

	def has_permission(self, request, view):
		"""Return True if the request carries the configured n8n callback secret."""
		secret = getattr(settings, "N8N_CALLBACK_SECRET", "")
		return bool(secret) and request.headers.get("X-N8n-Secret") == secret
