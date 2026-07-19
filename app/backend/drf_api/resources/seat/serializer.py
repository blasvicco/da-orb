"""Seat serializer"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MSeat
from drf_api.resources.auth.helpers import is_org_admin


class SSeat(serializers.ModelSerializer):
	"""Serializer for MSeat, annotated with the seat holder's current org-admin role."""

	role = serializers.SerializerMethodField()

	class Meta:
		model = MSeat
		fields = ["id", "username", "status", "role", "granted_on", "revoked_on"]

	def get_role(self, obj):
		"""Return 'admin' or 'standard' based on the seat holder's Django Group membership."""
		return "admin" if is_org_admin(obj.org, obj.username) else "standard"
