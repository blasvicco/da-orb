"""Seat permission"""

# App imports
from drf_api.resources import PIsOrgAdmin


class PSeat(PIsOrgAdmin):
	"""Seat/role management permission — org-admin only."""
