"""Base permission"""

# General imports
from rest_framework.permissions import BasePermission as DRFBasePermission


class BasePermission(DRFBasePermission):
	"""Base permission"""

	def has_permission(self, request, view):
		"""request view permission check fallback"""
		return request.user and request.user.is_superuser
