"""Chat session filters"""

# Lib imports
from django_filters import rest_framework as filters

# App imports
from drf_api.models import MChatSession
from drf_api.resources.base_filter import BaseFilterSet


class DFChatSession(BaseFilterSet):
	"""Chat session list filters: the shared created/updated day ranges, one project, and title search."""

	project_id = filters.NumberFilter(field_name="project_id")
	title__icontains = filters.CharFilter(field_name="title", lookup_expr="icontains")

	class Meta:
		fields = []
		model = MChatSession
