"""Request identity resolution helpers"""

# App imports
from drf_api.models import MOrganization
from drf_api.resources.auth.factory import FAuthenticator


def resolve_request_identity(request):
	"""Return (org, username, connection_key) from the request context."""
	# Resolved through the org's configured auth driver — each driver decides how much
	# to trust the request (e.g. B1S verifies its opaque token instead of headers).
	org, _ = MOrganization.get_by_slug(request.get_org_slug())
	if org is None:
		return None, "", ""

	driver = FAuthenticator.get_instance(
		driver=org.integration.get("auth_driver", "open_id"),
		integration=org.integration,
	)
	username, connection_key = driver.resolve_identity(request)
	return org, username, connection_key
