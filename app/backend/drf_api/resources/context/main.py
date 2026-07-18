"""DRF context viewset"""

# Lib imports
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

# App imports
from drf_api.models import MOrganization
from drf_api.resources.context.permission import PContext
from drf_api.resources.context.serializer import SContext


class VSContext(viewsets.ViewSet):
	"""Context View Set"""

	permission_classes = [PContext]

	@action(
		detail=False,
		methods=["get"],
	)
	def get(self, request, *args, **kwargs):
		"""Look and return the context for the given organization."""
		slug = request.get_org_slug()

		if not slug:
			raise NotFound("NOT_FOUND")

		org, _unused = MOrganization.get_by_slug(slug)
		if org is None:
			raise NotFound("NOT_FOUND")

		serializer = SContext(org)
		return Response(serializer.data)
