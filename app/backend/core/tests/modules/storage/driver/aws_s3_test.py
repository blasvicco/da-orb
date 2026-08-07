"""This module contains tests for the aws_s3 storage driver"""

# Lib imports
import pytest
from allure import step
from botocore.exceptions import ClientError

# App imports
from core.modules.storage.driver.aws_s3 import Instance
from core.modules.storage.exception import StorageError


def _configure(settings):
	"""Apply a consistent set of storage settings for a test."""
	settings.STORAGE_ACCESS_KEY = "test-access-key"
	settings.STORAGE_BUCKET_NAME = "test-bucket"
	settings.STORAGE_REGION = "us-east-1"
	settings.STORAGE_SECRET_KEY = "test-secret-key"


def _client_error():
	"""Build a minimal botocore ClientError."""
	return ClientError({"Error": {"Code": "500", "Message": "boom"}}, "GetObject")


def test_init_builds_client_without_an_endpoint_override(mocker, settings):
	"""Test Instance() builds a boto3 s3 client with no endpoint_url — real AWS S3 resolves its own"""

	with step("Arrange: Storage settings, boto3.client mocked."):
		_configure(settings)
		mock_client = mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")

	with step("Act: Instantiate Instance."):
		Instance()

	with step(
		"Assert: boto3.client called with credentials/region and no endpoint_url."
	):
		_, kwargs = mock_client.call_args
		assert mock_client.call_args[0] == ("s3",)
		assert kwargs["aws_access_key_id"] == "test-access-key"
		assert kwargs["aws_secret_access_key"] == "test-secret-key"
		assert kwargs["region_name"] == "us-east-1"
		assert "endpoint_url" not in kwargs


def test_delete(mocker, settings):
	"""Test delete() delegates to boto3's delete_object with the right params"""

	with step("Arrange: An Instance with a mocked boto3 client."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()

	with step("Act: Call delete"):
		instance.delete("org/db/session/1/2_file.csv")

	with step("Assert: delete_object called with the expected params"):
		instance._client.delete_object.assert_called_once_with(  # pylint: disable=protected-access
			Bucket="test-bucket", Key="org/db/session/1/2_file.csv"
		)


def test_delete_wraps_boto_errors(mocker, settings):
	"""Test delete() wraps a boto ClientError as StorageError"""

	with step("Arrange: An Instance whose client raises a ClientError."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()
		instance._client.delete_object.side_effect = (  # pylint: disable=protected-access
			_client_error()
		)

	with step("Act & Assert: StorageError is raised."):
		with pytest.raises(StorageError, match="org/db/session/1/2_file.csv"):
			instance.delete("org/db/session/1/2_file.csv")


def test_presigned_url(mocker, settings):
	"""Test presigned_url() delegates to boto3's generate_presigned_url with the right params"""

	with step("Arrange: An Instance with a mocked boto3 client."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()
		instance._client.generate_presigned_url.return_value = (  # pylint: disable=protected-access
			"https://signed.example/key"
		)

	with step("Act: Call presigned_url"):
		url = instance.presigned_url("org/db/session/1/2_file.csv", expires_in=120)

	with step("Assert: generate_presigned_url called with the expected params"):
		instance._client.generate_presigned_url.assert_called_once_with(  # pylint: disable=protected-access
			"get_object",
			Params={"Bucket": "test-bucket", "Key": "org/db/session/1/2_file.csv"},
			ExpiresIn=120,
		)
		assert url == "https://signed.example/key"


def test_presigned_url_wraps_boto_errors(mocker, settings):
	"""Test presigned_url() wraps a boto ClientError as StorageError"""

	with step("Arrange: An Instance whose client raises a ClientError."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()
		instance._client.generate_presigned_url.side_effect = (  # pylint: disable=protected-access
			_client_error()
		)

	with step("Act & Assert: StorageError is raised."):
		with pytest.raises(StorageError, match="org/db/session/1/2_file.csv"):
			instance.presigned_url("org/db/session/1/2_file.csv", expires_in=120)


@pytest.mark.parametrize(
	"payload",
	[
		{
			"content_type": "text/csv",
			"expected_extra_args": {"ContentType": "text/csv"},
			"description": "known content type is passed as ExtraArgs",
		},
		{
			"content_type": "",
			"expected_extra_args": None,
			"description": "empty content type passes no ExtraArgs",
		},
	],
)
def test_upload(mocker, settings, payload):
	"""Test upload() delegates to boto3's upload_file with the right params"""

	with step(f"Arrange: {payload['description']}"):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()

	with step("Act: Call upload"):
		instance.upload(
			"/tmp/file.csv", "org/db/session/1/2_file.csv", payload["content_type"]
		)

	with step("Assert: upload_file called with the expected params"):
		instance._client.upload_file.assert_called_once_with(  # pylint: disable=protected-access
			Filename="/tmp/file.csv",
			Bucket="test-bucket",
			Key="org/db/session/1/2_file.csv",
			ExtraArgs=payload["expected_extra_args"],
		)


def test_upload_wraps_boto_errors(mocker, settings):
	"""Test upload() wraps a boto ClientError as StorageError"""

	with step("Arrange: An Instance whose client raises a ClientError."):
		_configure(settings)
		mocker.patch("core.modules.storage.driver.aws_s3.boto3.client")
		instance = Instance()
		instance._client.upload_file.side_effect = (  # pylint: disable=protected-access
			_client_error()
		)

	with step("Act & Assert: StorageError is raised."):
		with pytest.raises(StorageError, match="org/db/session/1/2_file.csv"):
			instance.upload("/tmp/file.csv", "org/db/session/1/2_file.csv", "text/csv")
