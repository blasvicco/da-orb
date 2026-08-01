"""Chat serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MChatMessage, MChatSession


class SChatSession(serializers.ModelSerializer):
	"""Serializer for MChatSession list/detail."""

	pending = serializers.SerializerMethodField()
	tokens_used = serializers.SerializerMethodField()

	class Meta:
		model = MChatSession
		fields = [
			"id",
			"title",
			"created_on",
			"updated_on",
			"pending",
			"tokens_used",
			"n8n_state",
		]

	def get_pending(self, obj):
		"""True when the session's last message is from the user — no agent reply yet."""
		# The agent is presumably still working on it.
		last = obj.messages.last()
		return bool(last and last.type == "user")

	def get_tokens_used(self, obj):
		"""Read the `tokens_used` annotation added by VSChat.sessions(); 0 if absent/None."""
		return getattr(obj, "tokens_used", None) or 0


class SChatMessage(serializers.ModelSerializer):
	"""Serializer for MChatMessage list."""

	class Meta:
		model = MChatMessage
		fields = ["id", "type", "text", "extra", "timestamp"]
