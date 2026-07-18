"""Organization middleware"""


class MOrganizationMiddleware:
	"""Middleware to inject organization slug helper into request."""

	def __init__(self, get_response):
		"""Init middleware."""
		self.get_response = get_response

	def __call__(self, request):
		"""Inject slug resolution."""
		try:
			host = request.get_host().split(":")[0]
			slug = host.split(".")[0]
		except Exception:  # pylint: disable=broad-except
			slug = None

		request.get_org_slug = lambda: slug

		response = self.get_response(request)
		return response

