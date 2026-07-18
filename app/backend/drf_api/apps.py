"""Django app configuration"""

from django.apps import AppConfig


class DrfApiConfig(AppConfig):
	"""DRF API app configuration"""

	default_auto_field = "django.db.models.BigAutoField"
	name = "drf_api"
