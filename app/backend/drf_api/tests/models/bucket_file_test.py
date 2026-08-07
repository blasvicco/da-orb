"""This module contains tests for the MBucketFile model"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MBucketFile

pytestmark = pytest.mark.django_db


def test_build_storage_key(f_bucket_file):
	"""Test build_storage_key composes {org}/{database}/session/{session_id}/{id}_{name}"""

	with step("Arrange: A persisted bucket file linked to a session/org."):
		bucket_file = f_bucket_file.create(name="orders.csv")
		session = bucket_file.session

	with step("Act: Build the storage key."):
		key = bucket_file.build_storage_key()

	with step("Assert: Key follows the documented path shape, id-disambiguated."):
		expected = (
			f"{session.org.slug}/{session.connection_key}/session/"
			f"{session.id}/{bucket_file.id}_orders.csv"
		)
		assert key == expected


def test_build_storage_key_disambiguates_same_name_uploads(f_bucket_file):
	"""Test two same-named uploads in the same session get different storage keys"""

	with step("Arrange: Two bucket files with the same name in the same session."):
		session = f_bucket_file.create().session
		first = f_bucket_file.create(name="orders.csv", session=session)
		second = f_bucket_file.create(name="orders.csv", session=session)

	with step("Act: Build both storage keys."):
		first_key = first.build_storage_key()
		second_key = second.build_storage_key()

	with step("Assert: Keys differ despite the identical display name."):
		assert first_key != second_key


def test_cascades_on_session_deletion(f_bucket_file):
	"""Test deleting the linked chat session also deletes its bucket files"""

	with step("Arrange: A bucket file linked to a chat session."):
		bucket_file = f_bucket_file.create()
		session = bucket_file.session
		bucket_file_id = bucket_file.id

	with step("Act: Delete the chat session."):
		session.delete()

	with step("Assert: The bucket file no longer exists."):
		assert not MBucketFile.objects.filter(id=bucket_file_id).exists()


def test_str(f_bucket_file):
	"""Test __str__ returns a non-empty string"""

	with step("Arrange: A persisted bucket file."):
		bucket_file = f_bucket_file.create()

	with step("Assert: __str__ returns a non-empty string."):
		assert isinstance(str(bucket_file), str)
		assert len(str(bucket_file)) > 0
