"""This module contains tests for the project resource serializer"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization, MProject
from drf_api.resources.project.serializer import SProject

pytestmark = pytest.mark.django_db


def _make_project(**extra):
	"""Create a persisted MProject"""
	org = MOrganization.objects.create(name="acme", slug="acme")
	return MProject.objects.create(
		**{
			"connection_key": "TESTDB",
			"name": "Work",
			"org": org,
			"username": "bob",
			**extra,
		}
	)


def test_exposes_only_client_safe_fields():
	"""Test org, username, connection_key and deleted_on are never serialized"""

	with step("Arrange: A persisted project."):
		project = _make_project()

	with step("Act: Serialize it."):
		data = SProject(project).data

	with step("Assert: Exactly the documented fields are present."):
		assert set(data) == {
			"accessed_on",
			"chat_sessions_count",
			"created_on",
			"id",
			"is_default",
			"name",
			"summary",
			"updated_on",
		}


@pytest.mark.parametrize(
	"payload",
	[
		{"annotation": 4, "description": "an annotated count", "expected": 4},
		{"annotation": None, "description": "a null annotation", "expected": 0},
		{"annotation": "absent", "description": "no annotation at all", "expected": 0},
	],
)
def test_chat_sessions_count_reads_the_annotation(payload):
	"""Test chat_sessions_count reads VSProject's annotation, defaulting to 0 when absent or null"""

	with step(f"Arrange: A project with {payload['description']}."):
		project = _make_project()
		if payload["annotation"] != "absent":
			project.chat_sessions_count = payload["annotation"]

	with step("Act: Serialize it."):
		data = SProject(project).data

	with step("Assert: The count matches expectation."):
		assert data["chat_sessions_count"] == payload["expected"]


@pytest.mark.parametrize(
	"field, value",
	[
		("is_default", True),
		("id", 12345),
		("accessed_on", "2001-01-01T00:00:00Z"),
	],
)
def test_read_only_fields_are_ignored_on_write(field, value):
	"""Test a client cannot set is_default, id or the timestamps through the serializer"""

	with step(f"Arrange: A payload that tries to set read-only {field}."):
		serializer = SProject(data={"name": "Work", field: value})

	with step("Act: Validate."):
		valid = serializer.is_valid()

	with step("Assert: The payload is valid but the read-only field was dropped."):
		assert valid
		assert field not in serializer.validated_data


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_rejected(name):
	"""Test a project needs a non-blank name"""

	with step("Arrange: A payload with a blank name."):
		serializer = SProject(data={"name": name})

	with step("Act: Validate."):
		valid = serializer.is_valid()

	with step("Assert: The name is reported as invalid."):
		assert not valid
		assert "name" in serializer.errors
