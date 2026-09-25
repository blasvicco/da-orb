"""Project serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MProject


class SProject(serializers.ModelSerializer):
	"""Serializer for MProject — org/username/connection_key are never client-settable, so they're absent."""

	chat_sessions_count = serializers.SerializerMethodField()

	class Meta:
		fields = [
			"accessed_on",
			"chat_sessions_count",
			"created_on",
			"id",
			"is_default",
			"name",
			"summary",
			"updated_on",
		]
		model = MProject
		read_only_fields = [
			"accessed_on",
			"created_on",
			"id",
			"is_default",
			"updated_on",
		]

	def get_chat_sessions_count(self, obj):
		"""Read the `chat_sessions_count` annotation added by VSProject.get_queryset(); 0 if absent/None."""
		return getattr(obj, "chat_sessions_count", None) or 0
