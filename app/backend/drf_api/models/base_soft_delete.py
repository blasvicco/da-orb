"""Base soft-delete model"""

# Lib imports
from django.db import models
from django.utils import timezone

# App imports
from drf_api.models.base import MBase


class MBaseSoftDelete(MBase):
	"""Abstract base whose delete() marks deleted_on instead of removing the row, so any
	process still holding this row's id (e.g. an in-flight n8n callback) can keep
	referencing and updating it after a user-facing "delete"."""

	deleted_on = models.DateTimeField(blank=True, db_index=True, null=True)

	class Meta:
		abstract = True

	def delete(self, *args, **kwargs):
		"""Soft delete: set deleted_on and save, instead of removing the row."""
		self.deleted_on = timezone.now()
		self.save(update_fields=["deleted_on"])
