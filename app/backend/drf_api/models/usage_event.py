"""Usage tracking model — append-only log of token-usage and process-execution events"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.chat import MChatSession
from drf_api.models.organization import MOrganization


class MUsageEvent(MBase):
	"""One token-usage or process-execution event, emitted from the n8n callback."""

	# on_delete=SET_NULL on session (unlike MChatMessage, which cascades) — usage/audit
	# accounting must survive a user deleting their own chat history, or a user could
	# erase their own token-usage footprint from the admin dashboard by deleting the
	# conversation.

	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="usage_events",
	)
	username = models.CharField(max_length=150, db_index=True)
	connection_key = models.CharField(max_length=150, blank=True, default="")
	session = models.ForeignKey(
		MChatSession,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="usage_events",
	)
	event_type = models.CharField(
		max_length=20,
		choices=[
			("token_usage", "Token Usage"),
			("process_execution", "Process Execution"),
		],
		db_index=True,
	)
	occurred_on = models.DateTimeField(db_index=True)
	process_name = models.CharField(max_length=150, blank=True, default="")
	model_name = models.CharField(max_length=100, blank=True, default="")
	prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
	completion_tokens = models.PositiveIntegerField(null=True, blank=True)
	total_tokens = models.PositiveIntegerField(null=True, blank=True)

	class Meta:
		app_label = "drf_api"
		indexes = [
			models.Index(fields=["org", "event_type", "occurred_on"]),
			models.Index(fields=["org", "username", "event_type"]),
		]

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.org.slug}:{self.username}:{self.event_type}"
