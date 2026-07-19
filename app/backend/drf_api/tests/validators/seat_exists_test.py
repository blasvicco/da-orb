"""This module contains tests for the VSeatExists validator"""

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.validators import VSeatExists

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_returns_the_seat_when_found():
	"""Test VSeatExists returns the matching seat row"""

	with step("Arrange: A persisted seat for bob."):
		org = _make_org()
		seat = MSeat.objects.create(org=org, status="active", username="bob")

	with step("Act: Call VSeatExists."):
		result = VSeatExists()(org, "bob")

	with step("Assert: The seat is returned."):
		assert result.id == seat.id


def test_raises_seat_not_found_when_missing():
	"""Test VSeatExists raises SEAT_NOT_FOUND when no seat row exists"""

	with step("Arrange: An org with no seat for bob."):
		org = _make_org()

	with step("Act/Assert: VSeatExists raises SEAT_NOT_FOUND."):
		with pytest.raises(ValidationError, match="SEAT_NOT_FOUND"):
			VSeatExists()(org, "bob")


def test_custom_error_msg():
	"""Test VSeatExists raises the constructor-provided error_msg instead of the default"""

	with step("Arrange: An org with no seat for bob."):
		org = _make_org()

	with step("Act/Assert: VSeatExists raises the custom error code."):
		with pytest.raises(ValidationError, match="CUSTOM_CODE"):
			VSeatExists(error_msg="CUSTOM_CODE")(org, "bob")
