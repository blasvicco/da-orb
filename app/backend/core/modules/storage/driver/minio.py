"""MinIO storage driver — S3-compatible object storage for local/dev environments"""

# Lib imports
import boto3
from django.conf import settings

# App imports
from core.modules.storage.driver.aws_s3 import Instance as AwsS3Instance


class Instance(AwsS3Instance):
	"""Driver implementation for MinIO — reuses AwsS3's upload()/presigned_url(), only the client differs."""

	def _build_client(self):
		"""Build the boto3 client against the configured MinIO (S3-compatible) endpoint."""
		return boto3.client(
			"s3",
			aws_access_key_id=settings.STORAGE_ACCESS_KEY,
			aws_secret_access_key=settings.STORAGE_SECRET_KEY,
			endpoint_url=settings.STORAGE_ENDPOINT_URL,
			region_name=settings.STORAGE_REGION,
		)
