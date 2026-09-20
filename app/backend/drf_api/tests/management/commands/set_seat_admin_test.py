"""This module contains tests for the set_seat_admin management command"""

# Lib imports
import pytest
from allure import step
from django.core.management import CommandError, call_command

# App imports
from drf_api.resources.auth.helpers import is_org_admin
from drf_api.tests.factories import FOrganization, FSeat

pytestmark = pytest.mark.django_db


def test_grants_admin_for_existing_seat():
	"""Test set_seat_admin grants org-admin access to an existing seat"""

	with step("Arrange: An org with an active seat for bob."):
		org = FOrganization.create()
		FSeat.create(org=org, username="bob")

	with step("Act: Call the set_seat_admin command."):
		call_command("set_seat_admin", org.slug, "bob")

	with step("Assert: bob is now an org-admin."):
		assert is_org_admin(org, "bob") is True


def test_raises_when_org_not_found():
	"""Test set_seat_admin raises CommandError when the org slug doesn't exist"""

	with step("Arrange: No org exists with this slug."):
		pass

	with step("Act/Assert: The command raises CommandError."):
		with pytest.raises(CommandError, match="No organization found"):
			call_command("set_seat_admin", "does-not-exist", "bob")


def test_raises_when_seat_not_found():
	"""Test set_seat_admin raises CommandError when no seat exists for the username"""

	with step("Arrange: An org with no seat for bob."):
		org = FOrganization.create()

	with step("Act/Assert: The command raises CommandError."):
		with pytest.raises(CommandError, match="No seat found"):
			call_command("set_seat_admin", org.slug, "bob")
