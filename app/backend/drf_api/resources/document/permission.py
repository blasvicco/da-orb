"""Document permission"""

# App imports
from drf_api.resources.chat.permission import PN8nCallback


class PDocumentWrite(PN8nCallback):
	"""Workflow-generated document write permission — shared secret only, server-to-server."""
