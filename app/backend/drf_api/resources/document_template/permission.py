"""Document template permission"""

# App imports
from drf_api.resources import PIsOrgAdmin


class PDocumentTemplate(PIsOrgAdmin):
	"""Document template management permission — org-admin only."""
