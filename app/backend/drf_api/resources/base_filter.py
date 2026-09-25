"""Base filter set"""

# Lib imports
from django_filters import rest_framework as filters


class BaseFilterSet(filters.FilterSet):
	"""Filters every list resource with created_on/updated_on shares, named after the `<field>__<lookup>` query params the shared table component sends.

	Datetime bounds compare by calendar day (date__gte / date__lte), because the table sends a
	bare YYYY-MM-DD: a plain `lte` would parse it as midnight and exclude that whole day."""

	created_on__gte = filters.DateFilter(
		field_name="created_on", lookup_expr="date__gte"
	)
	created_on__lte = filters.DateFilter(
		field_name="created_on", lookup_expr="date__lte"
	)
	updated_on__gte = filters.DateFilter(
		field_name="updated_on", lookup_expr="date__gte"
	)
	updated_on__lte = filters.DateFilter(
		field_name="updated_on", lookup_expr="date__lte"
	)
