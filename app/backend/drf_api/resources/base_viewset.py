"""Base view set"""

# General imports
from rest_framework import viewsets

# App imports
from drf_api.resources import BasePermission, BaseSerializer


class BaseViewSet(viewsets.ModelViewSet):  # pylint: disable=too-many-ancestors
	"""Base view set"""

	permission_classes = [BasePermission]
	serializer_class = BaseSerializer

	def get_queryset(self):
		"""Return the configured queryset, excluding soft-deleted rows when the model supports it."""
		queryset = super().get_queryset()
		field_names = {field.name for field in queryset.model._meta.get_fields()}
		if "deleted_on" in field_names:
			queryset = queryset.filter(deleted_on__isnull=True)
		return queryset
