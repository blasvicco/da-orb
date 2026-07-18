"""DRF API URL Configuration"""
# pylint: disable=invalid-name

import importlib
import os

from django.urls import include, path
from humps import pascalize
from rest_framework import routers


class BaseRouter(routers.DefaultRouter):
	"""Override router to calculate properly the basename"""

	def register(self, prefix, viewset, basename=None):
		if hasattr(viewset, "queryset") and viewset.queryset is not None:
			basename = self.get_default_basename(viewset)
		self.registry.append((prefix, viewset, basename))

		# invalidate the urls cache
		if hasattr(self, "_urls"):
			del self._urls


# helper to look for all the available resources within the application and dynamically load the routes
print("INFO: Looking for DRF API resources to register.")
router = BaseRouter()
app_dir = os.path.dirname(__file__)
resources_path = os.path.join(app_dir, "resources")
if os.path.isdir(resources_path):
	for resource_name in os.listdir(resources_path):
		resource_path = os.path.join(resources_path, resource_name)
		if os.path.isdir(resource_path) and "__pycache__" not in resource_path:
			module = f"drf_api.resources.{resource_name}"
			reference = importlib.import_module(module)
			class_name = f"VS{pascalize(resource_name)}"
			print(
				f"Registering route: {resource_name} from {module} importing {class_name}"
			)
			router.register(
				f"{resource_name}",
				getattr(reference, class_name),
				basename=f"{resource_name}",
			)

urlpatterns = [
	path("", include(router.urls)),
]
