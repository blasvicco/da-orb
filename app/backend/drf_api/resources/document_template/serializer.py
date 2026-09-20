"""Document template serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MDocumentTemplate


class SDocumentTemplate(serializers.ModelSerializer):
	"""Serializer for MDocumentTemplate — storage_path is deliberately excluded, never exposed to the client."""

	class Meta:
		model = MDocumentTemplate
		fields = [
			"id",
			"document_type",
			"name",
			"is_default",
			"business_partner_ref",
			"language",
			"original_filename",
			"created_on",
			"updated_on",
		]
