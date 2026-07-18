"""Context permission"""

# App imports
from drf_api.resources import BasePermission


class PContext(BasePermission):
	"""Context permission"""

	def has_permission(self, request, view):
		"""request view permission check fallback"""
		# TODO: Maybe add another check?
		return view.action == "get"
