"""Context serializer"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MOrganization


class SContext(serializers.ModelSerializer):
	"""Serializes MOrganization for the public /api/context response — secrets are never exposed."""

	# auth_driver and base_url are only populated for open_id orgs.
	# client_id is the public OAuth client ID (open_id only).
	auth_driver = serializers.SerializerMethodField(method_name="get_auth_driver")
	base_url = serializers.SerializerMethodField(method_name="get_base_url")
	client_id = serializers.SerializerMethodField(method_name="get_client_id")

	def get_auth_driver(self, obj):
		"""Return the configured auth driver; defaults to open_id."""
		return obj.integration.get("auth_driver", "open_id")

	def get_base_url(self, obj):
		"""Return the SAP XSUAA authorization endpoint (open_id only)."""
		return obj.integration.get("base_url", "")

	def get_client_id(self, obj):
		"""Return the public OAuth client ID (open_id only)."""
		if obj.integration.get("auth_driver", "open_id") != "open_id":
			return ""
		return obj.integration.get("client_id", "")

	class Meta:
		model = MOrganization
		fields = [
			"auth_driver",
			"base_url",
			"client_id",
		]
