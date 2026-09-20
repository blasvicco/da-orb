"""Seat permission"""

# App imports
from drf_api.models import MSeat
from drf_api.resources import PIsOrgAdmin
from drf_api.resources.auth.helpers import resolve_request_identity
from drf_api.resources.base_permission import BasePermission


class PHasActiveSeat(BasePermission):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	def has_permission(self, request, view):
		"""Return True if the request carries a non-empty Bearer token and an active seat."""
		auth = request.headers.get("Authorization", "")
		if not (auth.startswith("Bearer ") and bool(auth[7:])):
			return False
		org, username, _ = resolve_request_identity(request)
		if org is None or not username:
			return False
		return MSeat.has_active_seat(org, username)


class PSeat(PIsOrgAdmin):
	"""Seat/role management permission — org-admin only."""
