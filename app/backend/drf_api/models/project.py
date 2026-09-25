"""Project model"""

# Lib imports
from django.db import models
from django.utils import timezone

# App imports
from drf_api.models.base_soft_delete import MBaseSoftDelete
from drf_api.models.organization import MOrganization


class MProject(MBaseSoftDelete):
	"""A named group of chat sessions, scoped to one (org, username, connection_key) identity.

	Every identity owns exactly one Default project (is_default) that is created on demand,
	can never be deleted or renamed, and is where a chat lands when no other project is chosen.
	Soft-deleted (deleted_on set) like its chat sessions, via MBaseSoftDelete."""

	accessed_on = models.DateTimeField(auto_now_add=True, db_index=True)
	connection_key = models.CharField(blank=True, default="", max_length=150)
	created_on = models.DateTimeField(auto_now_add=True)
	is_default = models.BooleanField(default=False)
	name = models.CharField(max_length=200)
	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="projects",
	)
	summary = models.TextField(blank=True, default="")
	updated_on = models.DateTimeField(auto_now=True)
	username = models.CharField(db_index=True, max_length=150)

	class Meta:
		app_label = "drf_api"
		constraints = [
			models.UniqueConstraint(
				condition=models.Q(is_default=True),
				fields=["org", "username", "connection_key"],
				name="unique_default_project_per_identity",
			)
		]
		indexes = [models.Index(fields=["org", "username", "connection_key"])]
		ordering = ["-accessed_on"]

	@classmethod
	def get_or_create_default(cls, org, username, connection_key):
		"""Return this identity's Default project, creating it if it doesn't exist yet."""
		return cls.objects.get_or_create(
			connection_key=connection_key,
			defaults={"name": "Default"},
			is_default=True,
			org=org,
			username=username,
		)[0]

	@classmethod
	def resolve_for_chat(cls, org, username, connection_key, project_id):
		"""Return the requested (owned, non-deleted) project, or the Default as fallback; bumps accessed_on."""
		project = None
		if project_id:
			project = cls.objects.filter(
				connection_key=connection_key,
				deleted_on__isnull=True,
				id=project_id,
				org=org,
				username=username,
			).first()
		project = project or cls.get_or_create_default(org, username, connection_key)
		cls.objects.filter(pk=project.pk).update(accessed_on=timezone.now())
		return project

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.name}"
