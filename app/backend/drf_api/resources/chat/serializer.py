"""Chat serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MChatMessage, MChatSession


class SChatSession(serializers.ModelSerializer):
	"""Serializer for MChatSession list/detail."""

	pending = serializers.SerializerMethodField()

	class Meta:
		model = MChatSession
		fields = ["id", "title", "created_on", "updated_on", "pending"]

	def get_pending(self, obj):
		"""True when the session's last message is from the user — no agent reply yet."""
		# The agent is presumably still working on it.
		last = obj.messages.last()
		return bool(last and last.type == "user")


class SChatMessage(serializers.ModelSerializer):
	"""Serializer for MChatMessage list."""

	class Meta:
		model = MChatMessage
		fields = ["id", "type", "text", "extra", "timestamp"]
