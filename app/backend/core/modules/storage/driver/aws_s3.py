"""AWS S3 storage driver"""

# General imports
import os
import tempfile

# Lib imports
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

# App imports
from core.modules.storage.driver.abstract import AStorage
from core.modules.storage.exception import StorageError


class Instance(AStorage):
	"""Driver implementation for AWS S3."""

	def __init__(self):
		"""Constructor"""
		self._client = self._build_client()

	def delete(self, dest_path):
		"""Delete the object at key dest_path from the bucket."""
		try:
			self._client.delete_object(
				Bucket=settings.STORAGE_BUCKET_NAME, Key=dest_path
			)
		except (BotoCoreError, ClientError) as error:
			raise StorageError(
				f"Delete failed for key '{dest_path}': {error}"
			) from error

	def download(self, dest_path):
		"""Download the object at key dest_path and return the local path it was written to."""
		local_path = tempfile.mktemp(suffix=os.path.splitext(dest_path)[1])
		try:
			self._client.download_file(
				Bucket=settings.STORAGE_BUCKET_NAME, Key=dest_path, Filename=local_path
			)
		except (BotoCoreError, ClientError) as error:
			raise StorageError(
				f"Download failed for key '{dest_path}': {error}"
			) from error
		return local_path

	def presigned_url(self, dest_path, expires_in=300):
		"""Return a presigned GET URL for dest_path, valid for expires_in seconds."""
		try:
			return self._client.generate_presigned_url(
				"get_object",
				Params={"Bucket": settings.STORAGE_BUCKET_NAME, "Key": dest_path},
				ExpiresIn=expires_in,
			)
		except (BotoCoreError, ClientError) as error:
			raise StorageError(
				f"Presigned URL generation failed for key '{dest_path}': {error}"
			) from error

	def upload(self, src_path, dest_path, content_type=""):
		"""Upload the file at src_path to the bucket at key dest_path."""
		try:
			self._client.upload_file(
				Filename=src_path,
				Bucket=settings.STORAGE_BUCKET_NAME,
				Key=dest_path,
				ExtraArgs={"ContentType": content_type} if content_type else None,
			)
		except (BotoCoreError, ClientError) as error:
			raise StorageError(
				f"Upload failed for key '{dest_path}': {error}"
			) from error

	def _build_client(self):
		"""Build the boto3 S3 client — overridden by drivers pointing at an S3-compatible endpoint."""
		return boto3.client(
			"s3",
			aws_access_key_id=settings.STORAGE_ACCESS_KEY,
			aws_secret_access_key=settings.STORAGE_SECRET_KEY,
			region_name=settings.STORAGE_REGION,
		)
