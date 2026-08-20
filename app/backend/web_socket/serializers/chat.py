"""Chat WebSocket message serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.resources.base_serializer import BaseStrictSerializer


# pylint: disable-next=abstract-method
class SMessageSend(BaseStrictSerializer):
	"""Enforces the `message.send` WebSocket contract — the frontend must send exactly
	these fields and no others; anything else means the frontend needs fixing, not this
	serializer filtering it out."""

	bucket_file_ids = serializers.ListField(
		child=serializers.IntegerField(), default=list, required=False
	)
	expertise_level = serializers.IntegerField(min_value=1, max_value=3)
	language = serializers.CharField()
	message = serializers.CharField(allow_blank=True, default="", required=False)


# pylint: disable-next=abstract-method
class SActiveNodeSwitch(BaseStrictSerializer):
	"""Enforces the `active_node.switch` WebSocket contract."""

	active_node_id = serializers.CharField(
		allow_null=True, default=None, required=False
	)
	# Fully-resolved, already-translated announcement text (e.g. "Context switched —
	# now in **Purchase Request**.") for the system bubble this switch produces —
	# built client-side since only the frontend knows the user's active locale.
	# Blank/absent means don't announce (e.g. tests exercising the Redis-state move
	# in isolation), so nothing gets broadcast or persisted.
	text = serializers.CharField(allow_blank=True, default="", required=False)
