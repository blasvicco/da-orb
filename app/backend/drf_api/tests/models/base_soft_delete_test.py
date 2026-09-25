"""This module contains tests for MBaseSoftDelete's delete() override"""

# Lib imports
import pytest
from allure import step
from django.utils import timezone

# App imports
from drf_api.models import MChatSession, MOrganization, MProject

pytestmark = pytest.mark.django_db


def test_delete_marks_deleted_on_instead_of_removing_the_row():
	"""Test delete() sets deleted_on and keeps the row, rather than removing it"""

	with step("Arrange: A persisted MChatSession (extends MBaseSoftDelete)."):
		org = MOrganization.objects.create(name="acme", slug="acme")
		session = MChatSession.objects.create(
			org=org,
			project=MProject.get_or_create_default(org, "bob", ""),
			username="bob",
		)

	with step("Act: Call delete()."):
		session.delete()

	with step(
		"Assert: The row still exists, with deleted_on set to a recent timestamp."
	):
		assert MChatSession.objects.filter(id=session.id).exists()
		session.refresh_from_db()
		assert session.deleted_on is not None
		assert session.deleted_on <= timezone.now()
