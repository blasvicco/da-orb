"""Session-scoped file bucket model"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.chat import MChatSession


class MBucketFile(MBase):
	"""One file (user-uploaded or workflow-generated) stored against a chat session's bucket."""

	session = models.ForeignKey(
		MChatSession,
		on_delete=models.CASCADE,
		related_name="bucket_files",
	)
	name = models.CharField(max_length=255)
	origin = models.CharField(
		max_length=20,
		choices=[
			("user_upload", "User Upload"),
			("workflow_generated", "Workflow Generated"),
		],
		default="user_upload",
	)
	mime_type = models.CharField(max_length=100, blank=True, default="")
	size = models.PositiveIntegerField(default=0)
	# Object-store key — set once the bytes are written to storage, after the
	# row is created (the row's own pk feeds into the key, see build_storage_key).
	storage_path = models.CharField(max_length=500, blank=True, default="")
	description = models.CharField(max_length=255, blank=True, default="")
	created_on = models.DateTimeField(auto_now_add=True, db_index=True)
	# Cached output of the workflow's extraction sub-workflow — populated on first
	# extraction, reused on every later lookup so the same file is never re-parsed.
	# Files are immutable after upload, so this needs no invalidation logic.
	extracted_content = models.TextField(blank=True, null=True, default=None)

	class Meta:
		app_label = "drf_api"
		ordering = ["-created_on"]

	def build_storage_key(self) -> str:
		"""Return this row's object-store key: {org}/{database}/session/{session_id}/{id}_{name}."""
		# The row's own id is folded into the key (not just {org}/.../{name} as
		# literally spelled out in the feature doc) so two same-named uploads in
		# the same session never overwrite each other's bytes in the bucket.
		return (
			f"{self.session.org.slug}/{self.session.connection_key}/session/"
			f"{self.session_id}/{self.id}_{self.name}"
		)

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.session_id}:{self.name}"
