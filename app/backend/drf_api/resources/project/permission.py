"""Project permission"""

# App imports
from drf_api.resources import PHasActiveSeat


class PProject(PHasActiveSeat):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	# Project ownership itself is enforced by the view's own queryset (org/username/
	# connection_key-scoped get_queryset()), not here.
