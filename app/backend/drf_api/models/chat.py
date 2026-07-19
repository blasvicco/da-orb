"""Chat session and message models"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.organization import MOrganization


class MChatSession(models.Model):
	"""Persisted record of one WebSocket chat session."""

	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="chat_sessions",
	)
	username = models.CharField(max_length=150, db_index=True)
	connection_key = models.CharField(max_length=150, blank=True, default="")
	title = models.CharField(max_length=200, blank=True)
	language = models.CharField(max_length=10, default="es")
	n8n_state = models.JSONField(null=True, blank=True)
	created_on = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_on = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [models.Index(fields=["org", "username", "connection_key"])]
		ordering = ["-updated_on"]


class MChatMessage(models.Model):
	"""One message within a chat session."""

	session = models.ForeignKey(
		MChatSession,
		on_delete=models.CASCADE,
		related_name="messages",
	)
	type = models.CharField(max_length=20)
	text = models.TextField()
	extra = models.JSONField(null=True, blank=True)
	timestamp = models.DateTimeField(db_index=True)

	class Meta:
		ordering = ["timestamp"]
