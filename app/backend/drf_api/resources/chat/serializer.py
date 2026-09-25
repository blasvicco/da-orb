"""Chat serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MChatMessage, MChatSession
from drf_api.resources.base_serializer import BaseStrictSerializer


class SChatSession(serializers.ModelSerializer):
	"""Serializer for MChatSession list/detail."""

	pending = serializers.SerializerMethodField()
	project_name = serializers.CharField(read_only=True, source="project.name")
	tokens_used = serializers.SerializerMethodField()

	class Meta:
		model = MChatSession
		fields = [
			"id",
			"title",
			"created_on",
			"updated_on",
			"pending",
			"project",
			"project_name",
			"tokens_used",
			"n8n_state",
		]

	def get_pending(self, obj):
		"""True when the session's last message is from the user — no agent reply yet."""
		# The agent is presumably still working on it. Reads the `last_message_type` annotation
		# added by VSChat's list queries, so serializing N chats costs no extra queries. There is
		# deliberately no per-row fallback: an unannotated queryset should fail loudly here, not
		# silently turn back into one query per chat.
		return obj.last_message_type == "user"

	def get_tokens_used(self, obj):
		"""Read the `tokens_used` annotation added by VSChat's list queries; 0 if absent/None."""
		return getattr(obj, "tokens_used", None) or 0


class SChatMessage(serializers.ModelSerializer):
	"""Serializer for MChatMessage list."""

	class Meta:
		model = MChatMessage
		fields = ["id", "type", "text", "extra", "timestamp"]


# pylint: disable-next=abstract-method
class SN8nCallback(BaseStrictSerializer):
	"""Enforces the async-result contract n8n posts back once a workflow run completes —
	these are the only fields n8n_callback reads, see its own docstring for what each one
	means. n8n sending anything outside this set means the n8n workflow needs fixing, not
	this serializer filtering it out."""

	extra = serializers.DictField(allow_null=True, default=dict, required=False)
	group_name = serializers.CharField(allow_blank=True, default="", required=False)
	processes = serializers.ListField(allow_null=True, default=None, required=False)
	root_execution_id = serializers.CharField(
		allow_blank=True, allow_null=True, default=None, required=False
	)
	session_id = serializers.IntegerField(allow_null=True, default=None, required=False)
	state = serializers.DictField(allow_null=True, default=dict, required=False)
	text = serializers.CharField(allow_blank=True, default="", required=False)
	type = serializers.CharField(default="agent", required=False)
