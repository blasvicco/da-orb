"""Chat session list serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MChatSession


class SChatSessionItem(serializers.ModelSerializer):
	"""One row of the chat list table: only what its columns show — no messages, no n8n state."""

	project_name = serializers.CharField(read_only=True, source="project.name")
	tokens_used = serializers.SerializerMethodField()

	class Meta:
		fields = [
			"created_on",
			"id",
			"project",
			"project_name",
			"title",
			"tokens_used",
			"updated_on",
		]
		model = MChatSession
		read_only_fields = ["created_on", "id", "project", "title", "updated_on"]

	def get_tokens_used(self, obj):
		"""Read the `tokens_used` annotation added by VSChatSession.get_queryset()."""
		# A method field rather than a plain IntegerField on purpose: DRF silently omits a
		# read-only field whose attribute is missing, whereas here an unannotated queryset
		# raises instead of quietly dropping the column (or costing a query per row).
		return obj.tokens_used
