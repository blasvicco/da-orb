"""Bucket serializers"""

# Lib imports
from rest_framework import serializers

# App imports
from drf_api.models import MBucketFile


class SBucketFile(serializers.ModelSerializer):
	"""Serializer for MBucketFile list — storage_path is deliberately excluded, never exposed to the client."""

	class Meta:
		model = MBucketFile
		fields = [
			"id",
			"name",
			"origin",
			"mime_type",
			"size",
			"created_on",
			"description",
		]
