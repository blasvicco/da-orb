"""Project filters"""

# Lib imports
from django_filters import rest_framework as filters

# App imports
from drf_api.models import MProject
from drf_api.resources.base_filter import BaseFilterSet


class DFProject(BaseFilterSet):
	"""Project list filters: the shared created/updated day ranges, plus last-accessed and text search."""

	accessed_on__gte = filters.DateFilter(
		field_name="accessed_on", lookup_expr="date__gte"
	)
	accessed_on__lte = filters.DateFilter(
		field_name="accessed_on", lookup_expr="date__lte"
	)
	name__icontains = filters.CharFilter(field_name="name", lookup_expr="icontains")
	summary__icontains = filters.CharFilter(
		field_name="summary", lookup_expr="icontains"
	)

	class Meta:
		fields = []
		model = MProject
