"""Bucket permission"""

# App imports
from drf_api.resources import PHasActiveSeat


class PBucket(PHasActiveSeat):
	"""Require a non-empty Bearer token for a user holding an active seat."""

	# Session/file ownership itself is enforced by the view's own lookups
	# (org/username/connection_key-scoped get_object_or_404 calls), not here.
