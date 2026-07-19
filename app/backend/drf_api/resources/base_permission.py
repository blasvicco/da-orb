"""Base permission"""

# General imports
from rest_framework.permissions import BasePermission as DRFBasePermission


class BasePermission(DRFBasePermission):
	"""Base permission"""

	def has_permission(self, request, view):
		"""request view permission check fallback"""
		return request.user and request.user.is_superuser


class PIsOrgAdmin(DRFBasePermission):
	"""Require the requester to hold the org-admin role for their org."""

	def has_permission(self, request, view):
		"""Return True if the resolved identity belongs to the org's admin group."""
		# Deferred import: drf_api.resources.auth pulls in drf_api.resources.auth.permission,
		# which imports drf_api.resources.BasePermission — importing this at module load time
		# would create a circular import with this very module.
		from drf_api.resources.auth.helpers import (  # pylint: disable=import-outside-toplevel
			is_org_admin,
			resolve_request_identity,
		)

		org, username, _ = resolve_request_identity(request)
		if org is None or not username:
			return False
		return is_org_admin(org, username)
