"""Auth permission"""

# App imports
from drf_api.resources import BasePermission


class PAuth(BasePermission):
	"""Auth permission"""

	def has_permission(self, request, view):
		"""request view permission check fallback"""
		return view.action in ("callback", "login", "refresh")
