"""Chat session permission"""

# App imports
from drf_api.resources import PHasActiveSeat


class PChatSession(PHasActiveSeat):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	# Chat ownership itself is enforced by the view's own queryset and lookups
	# (org/username/connection_key-scoped), not here.
