"""Auth permission"""

# App imports
from drf_api.resources import BasePermission
from drf_api.resources.auth.helpers import is_org_admin, resolve_request_identity


class PAuth(BasePermission):
	"""Auth permission"""

	def has_permission(self, request, view):
		"""request view permission check fallback"""
		return view.action in ("callback", "login", "refresh")


class PIsOrgAdmin(BasePermission):
	"""Require the requester to hold the org-admin role for their org."""

	def has_permission(self, request, view):
		"""Return True if the resolved identity belongs to the org's admin group."""
		org, username, _ = resolve_request_identity(request)
		if org is None or not username:
			return False
		return is_org_admin(org, username)
