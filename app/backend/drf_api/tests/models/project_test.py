"""This module contains tests for the MProject model"""

# General imports
from datetime import timedelta

# Lib imports
import pytest
from allure import step
from django.db import IntegrityError, transaction
from django.utils import timezone

# App imports
from drf_api.models import MChatSession, MOrganization, MProject

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_get_or_create_default_creates_it_once_per_identity():
	"""Test get_or_create_default creates the Default project on first use and returns the same row afterwards"""

	with step("Arrange: An organization with no projects."):
		org = _make_org()

	with step("Act: Call get_or_create_default twice."):
		first = MProject.get_or_create_default(org, "bob", "TESTDB")
		second = MProject.get_or_create_default(org, "bob", "TESTDB")

	with step("Assert: One locked Default project was created and reused."):
		assert first.id == second.id
		assert first.is_default is True
		assert first.name == "Default"
		assert MProject.objects.count() == 1


@pytest.mark.parametrize(
	"other",
	[
		{
			"connection_key": "OTHERDB",
			"description": "another connection_key",
			"username": "bob",
		},
		{
			"connection_key": "TESTDB",
			"description": "another user",
			"username": "alice",
		},
	],
)
def test_get_or_create_default_is_scoped_per_identity(other):
	"""Test each (org, username, connection_key) identity gets its own Default project"""

	with step(
		f"Arrange: A Default project for bob/TESTDB, and an identity with {other['description']}."
	):
		org = _make_org()
		mine = MProject.get_or_create_default(org, "bob", "TESTDB")

	with step("Act: Call get_or_create_default for the other identity."):
		theirs = MProject.get_or_create_default(
			org, other["username"], other["connection_key"]
		)

	with step("Assert: A distinct Default project was created."):
		assert theirs.id != mine.id
		assert theirs.is_default is True


def test_only_one_default_project_per_identity_is_allowed():
	"""Test the partial unique constraint rejects a second Default project, but allows any number of regular ones"""

	with step("Arrange: A Default project for bob/TESTDB."):
		org = _make_org()
		MProject.get_or_create_default(org, "bob", "TESTDB")

	with step("Act: Create two regular projects, then a second Default one."):
		MProject.objects.create(
			connection_key="TESTDB", name="A", org=org, username="bob"
		)
		MProject.objects.create(
			connection_key="TESTDB", name="B", org=org, username="bob"
		)
		with pytest.raises(IntegrityError), transaction.atomic():
			MProject.objects.create(
				connection_key="TESTDB",
				is_default=True,
				name="Second default",
				org=org,
				username="bob",
			)

	with step("Assert: Only the second Default project was refused."):
		assert MProject.objects.filter(is_default=True).count() == 1
		assert MProject.objects.count() == 3


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "an owned live project", "expected": "Work", "kwargs": {}},
		{
			"description": "a soft-deleted project",
			"expected": "Default",
			"kwargs": {"deleted_on": timezone.now()},
		},
		{
			"description": "another user's project",
			"expected": "Default",
			"kwargs": {"username": "alice"},
		},
		{
			"description": "another connection_key's project",
			"expected": "Default",
			"kwargs": {"connection_key": "OTHERDB"},
		},
	],
)
def test_resolve_for_chat_returns_requested_project_or_falls_back(payload):
	"""Test resolve_for_chat returns the requested project only if it is owned and live, else the Default project"""

	with step(f"Arrange: A project id that names {payload['description']}."):
		org = _make_org()
		requested = MProject.objects.create(
			**{
				"connection_key": "TESTDB",
				"name": "Work",
				"org": org,
				"username": "bob",
				**payload["kwargs"],
			}
		)

	with step("Act: Call resolve_for_chat."):
		project = MProject.resolve_for_chat(org, "bob", "TESTDB", requested.id)

	with step("Assert: The expected project was returned."):
		assert project.name == payload["expected"]


@pytest.mark.parametrize("project_id", [None, 0, 999999])
def test_resolve_for_chat_falls_back_to_default_without_a_usable_id(project_id):
	"""Test resolve_for_chat returns (and creates on demand) the Default project when no valid id is given"""

	with step("Arrange: An organization with no projects."):
		org = _make_org()

	with step("Act: Call resolve_for_chat."):
		project = MProject.resolve_for_chat(org, "bob", "TESTDB", project_id)

	with step("Assert: The Default project was returned."):
		assert project.is_default is True


def test_resolve_for_chat_bumps_accessed_on():
	"""Test resolve_for_chat marks the resolved project as just accessed, so it sorts first in the selector"""

	with step("Arrange: A project last accessed long ago."):
		org = _make_org()
		project = MProject.objects.create(
			connection_key="TESTDB", name="Work", org=org, username="bob"
		)
		long_ago = timezone.now() - timedelta(days=30)
		MProject.objects.filter(pk=project.pk).update(accessed_on=long_ago)

	with step("Act: Call resolve_for_chat."):
		MProject.resolve_for_chat(org, "bob", "TESTDB", project.id)

	with step("Assert: accessed_on moved forward."):
		project.refresh_from_db()
		assert project.accessed_on > long_ago


def test_default_ordering_is_most_recently_accessed_first():
	"""Test projects list most-recently-accessed first by default"""

	with step("Arrange: Two projects, the second accessed more recently."):
		org = _make_org()
		older = MProject.objects.create(
			connection_key="TESTDB", name="Older", org=org, username="bob"
		)
		newer = MProject.objects.create(
			connection_key="TESTDB", name="Newer", org=org, username="bob"
		)
		MProject.objects.filter(pk=older.pk).update(
			accessed_on=timezone.now() - timedelta(days=1)
		)

	with step("Act: List all projects."):
		names = [project.name for project in MProject.objects.all()]

	with step("Assert: The more recently accessed project comes first."):
		assert names == [newer.name, older.name]


def test_delete_soft_deletes_and_keeps_its_chat_sessions_referencing_it():
	"""Test delete() marks deleted_on (MBaseSoftDelete) instead of removing the row or cascading to its sessions"""

	with step("Arrange: A project holding a chat session."):
		org = _make_org()
		project = MProject.objects.create(
			connection_key="TESTDB", name="Work", org=org, username="bob"
		)
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, project=project, username="bob"
		)

	with step("Act: Call delete()."):
		project.delete()

	with step("Assert: Both rows still exist, and the project is marked deleted."):
		project.refresh_from_db()
		assert project.deleted_on is not None
		assert MChatSession.objects.filter(pk=session.pk).exists()


def test_str():
	"""Test __str__ returns id:name"""

	with step("Arrange: A persisted project."):
		org = _make_org()
		project = MProject.objects.create(
			connection_key="TESTDB", name="Work", org=org, username="bob"
		)

	with step("Assert: __str__ is id:name."):
		assert str(project) == f"{project.id}:Work"
