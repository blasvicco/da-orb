"""This module contains tests for the bucket viewset"""

# General imports
from urllib.parse import urlencode

# Lib imports
import pytest
from allure import step
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

# App imports
from core.modules.storage.exception import StorageError
from drf_api.models import MBucketFile, MChatSession, MOrganization, MSeat
from drf_api.resources.bucket.main import VSBucket

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an active seat for the test user"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	MSeat.objects.create(org=org, status="active", username="bob")
	return org


def _make_request(method, org, data=None, query=None, username="bob"):
	"""Build a DRF-compatible request with org/auth headers already attached (connection_key is always TESTDB)"""
	build = getattr(_factory, method)
	path = f"/?{urlencode(query)}" if query else "/"
	kwargs = {"format": "multipart"} if data is not None else {}
	request = build(
		path,
		data=data,
		HTTP_AUTHORIZATION="Bearer sometoken",
		HTTP_X_SAP_CONNECTION_KEY="TESTDB",
		HTTP_X_SAP_USERNAME=username,
		**kwargs,
	)
	request.get_org_slug = lambda: org.slug
	return request


def test_files_returns_only_the_owned_session_bucket_files():
	"""Test files only returns rows belonging to the requested (owned) session"""

	with step("Arrange: A session with two files, and an unrelated session with one."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		other_session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		matching_one = MBucketFile.objects.create(name="a.csv", session=session, size=1)
		matching_two = MBucketFile.objects.create(name="b.csv", session=session, size=2)
		MBucketFile.objects.create(name="c.csv", session=other_session, size=3)
		request = _make_request("get", org, query={"session_id": session.id})

	with step("Act: Call files."):
		response = VSBucket.as_view({"get": "files"})(request)

	with step("Assert: Only the owned session's files are returned."):
		assert response.status_code == 200
		assert {row["id"] for row in response.data} == {
			matching_one.id,
			matching_two.id,
		}


def test_files_rejects_session_owned_by_another_user():
	"""Test files 404s when the session belongs to a different username"""

	with step("Arrange: A session owned by 'alice', requested as 'bob'."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		request = _make_request("get", org, query={"session_id": session.id})

	with step("Act: Call files."):
		response = VSBucket.as_view({"get": "files"})(request)

	with step("Assert: 404 is returned."):
		assert response.status_code == 404


def test_upload_creates_bucket_file_and_writes_to_storage(mocker):
	"""Test upload creates the MBucketFile row and writes its bytes to storage under the right key"""

	with step("Arrange: An owned session and a mocked storage driver."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		upload_file = SimpleUploadedFile(
			"orders.csv", b"a,b\n1,2", content_type="text/csv"
		)
		request = _make_request(
			"post",
			org,
			data={"session_id": session.id, "file": upload_file},
		)

	with step("Act: Call upload."):
		response = VSBucket.as_view({"post": "upload"})(request)

	with step(
		"Assert: The record is created and the driver's upload received the built key."
	):
		assert response.status_code == 201
		bucket_file = MBucketFile.objects.get(id=response.data["id"])
		assert bucket_file.name == "orders.csv"
		assert bucket_file.mime_type == "text/csv"
		assert bucket_file.size == len(b"a,b\n1,2")
		assert bucket_file.storage_path == bucket_file.build_storage_key()
		call_args = mock_fstorage.get_instance.return_value.upload.call_args
		assert isinstance(call_args[0][0], str) and call_args[0][0]
		assert call_args[0][1] == bucket_file.storage_path
		assert call_args[0][2] == "text/csv"


def test_upload_returns_400_and_discards_the_row_when_storage_upload_fails(mocker):
	"""Test upload deletes the just-created MBucketFile row when the driver's upload raises StorageError"""

	with step("Arrange: An owned session and a storage driver that fails to upload."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		mock_fstorage.get_instance.return_value.upload.side_effect = StorageError(
			"boom"
		)
		upload_file = SimpleUploadedFile(
			"orders.csv", b"a,b\n1,2", content_type="text/csv"
		)
		request = _make_request(
			"post",
			org,
			data={"session_id": session.id, "file": upload_file},
		)

	with step("Act: Call upload."):
		response = VSBucket.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned and the row is not left behind."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert not MBucketFile.objects.exists()


def test_upload_missing_file_returns_400(mocker):
	"""Test upload rejects a request with no file attached"""

	with step("Arrange: An owned session, no file in the payload."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		mocker.patch("drf_api.resources.bucket.main.FStorage")
		request = _make_request("post", org, data={"session_id": session.id})

	with step("Act: Call upload."):
		response = VSBucket.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned with MISSING_FILE."):
		assert response.status_code == 400
		assert response.data["error"] == "MISSING_FILE"


def test_upload_rejects_file_over_the_configured_size_limit(mocker, settings):
	"""Test upload rejects a file larger than settings.BUCKET_MAX_FILE_SIZE_MB"""

	with step("Arrange: A max size of 0MB and a non-empty file."):
		settings.BUCKET_MAX_FILE_SIZE_MB = 0
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		mocker.patch("drf_api.resources.bucket.main.FStorage")
		upload_file = SimpleUploadedFile("orders.csv", b"a,b\n1,2")
		request = _make_request(
			"post",
			org,
			data={"session_id": session.id, "file": upload_file},
		)

	with step("Act: Call upload."):
		response = VSBucket.as_view({"post": "upload"})(request)

	with step("Assert: 400 is returned with FILE_TOO_LARGE, and nothing is persisted."):
		assert response.status_code == 400
		assert response.data["error"] == "FILE_TOO_LARGE"
		assert not MBucketFile.objects.exists()


def test_upload_rejects_session_owned_by_another_user(mocker):
	"""Test upload 404s when the target session belongs to a different username"""

	with step("Arrange: A session owned by 'alice', uploaded as 'bob'."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		mocker.patch("drf_api.resources.bucket.main.FStorage")
		upload_file = SimpleUploadedFile("orders.csv", b"a,b\n1,2")
		request = _make_request(
			"post",
			org,
			data={"session_id": session.id, "file": upload_file},
		)

	with step("Act: Call upload."):
		response = VSBucket.as_view({"post": "upload"})(request)

	with step("Assert: 404 is returned, nothing is persisted."):
		assert response.status_code == 404
		assert not MBucketFile.objects.exists()


def test_download_returns_a_presigned_url(mocker):
	"""Test download returns the URL produced by the driver's presigned_url for the owned file"""

	with step(
		"Arrange: A bucket file owned by the requester, and a mocked storage driver."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv",
			session=session,
			size=1,
			storage_path="acme/TESTDB/session/1/1_orders.csv",
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		mock_fstorage.get_instance.return_value.presigned_url.return_value = (
			"https://signed.example/orders.csv"
		)
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call download."):
		response = VSBucket.as_view({"get": "download"})(request)

	with step(
		"Assert: The presigned URL is returned, built from the file's storage_path."
	):
		assert response.status_code == 200
		assert response.data == {"url": "https://signed.example/orders.csv"}
		mock_fstorage.get_instance.return_value.presigned_url.assert_called_once_with(
			bucket_file.storage_path, expires_in=300
		)


def test_download_returns_400_when_presigned_url_generation_fails(mocker):
	"""Test download returns 400 when the driver's presigned_url raises StorageError"""

	with step(
		"Arrange: A bucket file owned by the requester, and a failing storage driver."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv",
			session=session,
			size=1,
			storage_path="acme/TESTDB/session/1/1_orders.csv",
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		mock_fstorage.get_instance.return_value.presigned_url.side_effect = (
			StorageError("boom")
		)
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call download."):
		response = VSBucket.as_view({"get": "download"})(request)

	with step("Assert: 400 is returned."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"


def test_download_rejects_file_owned_by_another_session(mocker):
	"""Test download 404s when the file's session belongs to a different username"""

	with step("Arrange: A bucket file owned by 'alice', requested as 'bob'."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		mocker.patch("drf_api.resources.bucket.main.FStorage")
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call download."):
		response = VSBucket.as_view({"get": "download"})(request)

	with step("Assert: 404 is returned."):
		assert response.status_code == 404


def test_extraction_get_returns_none_when_never_extracted():
	"""Test extraction GET returns a null extracted_content for a file that was never extracted"""

	with step("Arrange: A bucket file owned by the requester, never extracted."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call extraction."):
		response = VSBucket.as_view({"get": "extraction"})(request)

	with step("Assert: extracted_content is null."):
		assert response.status_code == 200
		assert response.data == {"extracted_content": None}


def test_extraction_get_returns_the_cached_content():
	"""Test extraction GET returns the already-cached extracted_content without altering it"""

	with step("Arrange: A bucket file with previously cached extracted_content."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			extracted_content="a,b\n1,2",
			name="orders.csv",
			session=session,
			size=1,
		)
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call extraction."):
		response = VSBucket.as_view({"get": "extraction"})(request)

	with step("Assert: The cached content is returned as-is."):
		assert response.status_code == 200
		assert response.data == {"extracted_content": "a,b\n1,2"}


def test_extraction_patch_persists_the_content():
	"""Test extraction PATCH stores extracted_content on the owned file"""

	with step("Arrange: A bucket file owned by the requester, never extracted."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		request = _make_request(
			"patch",
			org,
			data={"extracted_content": "a,b\n1,2"},
			query={"file_id": bucket_file.id},
		)

	with step("Act: Call extraction."):
		response = VSBucket.as_view({"patch": "extraction"})(request)

	with step("Assert: The content is persisted and echoed back."):
		assert response.status_code == 200
		assert response.data == {"extracted_content": "a,b\n1,2"}
		bucket_file.refresh_from_db()
		assert bucket_file.extracted_content == "a,b\n1,2"


def test_extraction_rejects_file_owned_by_another_session():
	"""Test extraction 404s when the file's session belongs to a different username"""

	with step("Arrange: A bucket file owned by 'alice', requested as 'bob'."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		request = _make_request("get", org, query={"file_id": bucket_file.id})

	with step("Act: Call extraction."):
		response = VSBucket.as_view({"get": "extraction"})(request)

	with step("Assert: 404 is returned."):
		assert response.status_code == 404


def test_delete_file_removes_the_storage_object_and_the_row(mocker):
	"""Test delete_file deletes both the storage object and the MBucketFile row for an owned file"""

	with step(
		"Arrange: A bucket file owned by the requester, and a mocked storage driver."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv",
			session=session,
			size=1,
			storage_path="acme/TESTDB/session/1/1_orders.csv",
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		request = _make_request("delete", org, query={"file_id": bucket_file.id})

	with step("Act: Call delete_file."):
		response = VSBucket.as_view({"delete": "delete_file"})(request)

	with step(
		"Assert: 204 is returned, the driver deleted the storage key, and the row is gone."
	):
		assert response.status_code == 204
		mock_fstorage.get_instance.return_value.delete.assert_called_once_with(
			bucket_file.storage_path
		)
		assert not MBucketFile.objects.filter(id=bucket_file.id).exists()


def test_delete_file_skips_storage_delete_when_storage_path_is_blank(mocker):
	"""Test delete_file only removes the row (no storage call) when the file never got a storage_path"""

	with step("Arrange: A bucket file owned by the requester with no storage_path."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		request = _make_request("delete", org, query={"file_id": bucket_file.id})

	with step("Act: Call delete_file."):
		response = VSBucket.as_view({"delete": "delete_file"})(request)

	with step("Assert: 204 is returned, no storage call is made, and the row is gone."):
		assert response.status_code == 204
		mock_fstorage.get_instance.return_value.delete.assert_not_called()
		assert not MBucketFile.objects.filter(id=bucket_file.id).exists()


def test_delete_file_returns_400_and_keeps_the_row_when_storage_delete_fails(mocker):
	"""Test delete_file leaves the row intact when the driver's delete raises StorageError"""

	with step(
		"Arrange: A bucket file owned by the requester, and a storage driver that fails to delete."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv",
			session=session,
			size=1,
			storage_path="acme/TESTDB/session/1/1_orders.csv",
		)
		mock_fstorage = mocker.patch("drf_api.resources.bucket.main.FStorage")
		mock_fstorage.get_instance.return_value.delete.side_effect = StorageError(
			"boom"
		)
		request = _make_request("delete", org, query={"file_id": bucket_file.id})

	with step("Act: Call delete_file."):
		response = VSBucket.as_view({"delete": "delete_file"})(request)

	with step("Assert: 400 is returned and the row is kept, not deleted."):
		assert response.status_code == 400
		assert response.data["error"] == "boom"
		assert MBucketFile.objects.filter(id=bucket_file.id).exists()


def test_delete_file_rejects_file_owned_by_another_session(mocker):
	"""Test delete_file 404s when the file's session belongs to a different username"""

	with step("Arrange: A bucket file owned by 'alice', requested as 'bob'."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="alice"
		)
		bucket_file = MBucketFile.objects.create(
			name="orders.csv", session=session, size=1
		)
		mocker.patch("drf_api.resources.bucket.main.FStorage")
		request = _make_request("delete", org, query={"file_id": bucket_file.id})

	with step("Act: Call delete_file."):
		response = VSBucket.as_view({"delete": "delete_file"})(request)

	with step("Assert: 404 is returned and the row is untouched."):
		assert response.status_code == 404
		assert MBucketFile.objects.filter(id=bucket_file.id).exists()
