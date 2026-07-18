"""Base view set"""

# General imports
from rest_framework import viewsets

# App imports
from drf_api.resources import BasePermission, BaseSerializer


class BaseViewSet(viewsets.ModelViewSet):  # pylint: disable=too-many-ancestors
	"""Base view set"""

	permission_classes = [BasePermission]
	serializer_class = BaseSerializer
