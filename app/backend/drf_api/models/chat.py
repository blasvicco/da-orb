"""Chat session and message models"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.base_soft_delete import MBaseSoftDelete
from drf_api.models.organization import MOrganization
from drf_api.models.project import MProject


class MChatSession(MBaseSoftDelete):
	"""Persisted record of one WebSocket chat session.

	Soft-deleted (deleted_on set): stays queryable by pk for any in-flight process still
	holding the id (e.g. an n8n execution fired before the delete, or a background
	usage-recording walk) -- only user-facing listing/resume paths (VSChat.sessions,
	CChat._load_session) filter it out.

	Always belongs to exactly one project (see MProject.resolve_for_chat)."""

	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="chat_sessions",
	)
	project = models.ForeignKey(
		MProject,
		on_delete=models.CASCADE,
		related_name="chat_sessions",
	)
	username = models.CharField(max_length=150, db_index=True)
	connection_key = models.CharField(max_length=150, blank=True, default="")
	title = models.CharField(max_length=200, blank=True)
	n8n_state = models.JSONField(null=True, blank=True)
	created_on = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_on = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [models.Index(fields=["org", "username", "connection_key"])]
		ordering = ["-updated_on"]


class MChatMessage(MBase):
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
