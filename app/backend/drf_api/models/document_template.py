"""Org-scoped document render template model"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.organization import MOrganization


class MDocumentTemplate(MBase):
	"""One org-uploaded .rpt template for a given document type, optionally the org's default."""

	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="document_templates",
	)
	document_type = models.CharField(max_length=50)
	name = models.CharField(max_length=255)
	is_default = models.BooleanField(default=False)
	# Blank = no override — see document/main.py's _resolve_template_path() cascade.
	business_partner_ref = models.CharField(max_length=50, blank=True, default="")
	language = models.CharField(max_length=10, blank=True, default="")
	original_filename = models.CharField(max_length=255, blank=True, default="")
	# Object-store key — set once the bytes are written to storage, after the
	# row is created (the row's own pk feeds into the key, see build_storage_key).
	storage_path = models.CharField(max_length=500, blank=True, default="")
	created_on = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_on = models.DateTimeField(auto_now=True)

	class Meta:
		app_label = "drf_api"
		ordering = ["-created_on"]

	def build_storage_key(self) -> str:
		"""Return this row's object-store key: {org}/document_templates/{document_type}/{id}_{name}.rpt."""
		return f"{self.org.slug}/document_templates/{self.document_type}/{self.id}_{self.name}.rpt"

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.org_id}:{self.document_type}:{self.name}"
