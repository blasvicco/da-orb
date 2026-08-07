"""This module contains tests for the minio storage driver"""

# Lib imports
from allure import step

# App imports
from core.modules.storage.driver.aws_s3 import Instance as AwsS3Instance
from core.modules.storage.driver.minio import Instance


def _configure(settings):
	"""Apply a consistent set of storage settings for a test."""
	settings.STORAGE_ACCESS_KEY = "test-access-key"
	settings.STORAGE_BUCKET_NAME = "test-bucket"
	settings.STORAGE_ENDPOINT_URL = "http://minio.blas.local:9000"
	settings.STORAGE_REGION = "us-east-1"
	settings.STORAGE_SECRET_KEY = "test-secret-key"


def test_extends_aws_s3_instance(mocker, settings):
	"""Test the minio driver reuses aws_s3's Instance rather than reimplementing it"""

	with step("Arrange: Storage settings, boto3.client mocked."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.minio.boto3.client")

	with step("Act: Instantiate Instance."):
		instance = Instance()

	with step(
		"Assert: It is a full AwsS3Instance — upload()/presigned_url() come from there."
	):
		assert isinstance(instance, AwsS3Instance)


def test_init_builds_client_with_the_configured_endpoint(mocker, settings):
	"""Test Instance() builds a boto3 s3 client pointed at STORAGE_ENDPOINT_URL"""

	with step("Arrange: Storage settings, boto3.client mocked."):
		_configure(settings)
		mock_client = mocker.patch("core.modules.storage.driver.minio.boto3.client")

	with step("Act: Instantiate Instance."):
		Instance()

	with step(
		"Assert: boto3.client called with credentials/region and the endpoint_url."
	):
		_, kwargs = mock_client.call_args
		assert mock_client.call_args[0] == ("s3",)
		assert kwargs["aws_access_key_id"] == "test-access-key"
		assert kwargs["aws_secret_access_key"] == "test-secret-key"
		assert kwargs["region_name"] == "us-east-1"
		assert kwargs["endpoint_url"] == "http://minio.blas.local:9000"


def test_delete_presigned_url_and_upload_are_inherited_unchanged(mocker, settings):
	"""Test delete()/presigned_url()/upload() behave exactly like aws_s3's, just against a different client"""

	with step("Arrange: An Instance with a mocked boto3 client."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.minio.boto3.client")
		instance = Instance()
		instance._client.generate_presigned_url.return_value = (  # pylint: disable=protected-access
			"https://minio.example/key"
		)

	with step("Act: Call delete, presigned_url, and upload."):
		instance.delete("org/db/session/1/2_file.csv")
		url = instance.presigned_url("org/db/session/1/2_file.csv", expires_in=120)
		instance.upload("/tmp/file.csv", "org/db/session/1/2_file.csv", "text/csv")

	with step(
		"Assert: All three delegate to the same underlying client as aws_s3's Instance."
	):
		instance._client.delete_object.assert_called_once_with(  # pylint: disable=protected-access
			Bucket="test-bucket", Key="org/db/session/1/2_file.csv"
		)
		assert url == "https://minio.example/key"
		instance._client.upload_file.assert_called_once_with(  # pylint: disable=protected-access
			Filename="/tmp/file.csv",
			Bucket="test-bucket",
			Key="org/db/session/1/2_file.csv",
			ExtraArgs={"ContentType": "text/csv"},
		)
