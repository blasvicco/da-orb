"""This module contains tests for the VSeatCapacityAvailable validator"""

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.validators import VSeatCapacityAvailable

pytestmark = pytest.mark.django_db


def _make_org(seat_limit, slug="acme"):
	"""Create a persisted MOrganization instance with the given seat_limit"""
	return MOrganization.objects.create(name=slug, seat_limit=seat_limit, slug=slug)


def test_returns_the_org_when_capacity_available():
	"""Test VSeatCapacityAvailable passes through the org when under the seat limit"""

	with step("Arrange: An org with capacity for one more seat."):
		org = _make_org(seat_limit=1)

	with step("Act: Call VSeatCapacityAvailable."):
		result = VSeatCapacityAvailable()(org)

	with step("Assert: The same org is returned."):
		assert result is org


def test_raises_seat_limit_exceeded_when_at_capacity():
	"""Test VSeatCapacityAvailable raises SEAT_LIMIT_EXCEEDED once active seats reach the limit"""

	with step("Arrange: An org already at its seat limit."):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="active", username="alice")

	with step("Act/Assert: VSeatCapacityAvailable raises SEAT_LIMIT_EXCEEDED."):
		with pytest.raises(ValidationError, match="SEAT_LIMIT_EXCEEDED"):
			VSeatCapacityAvailable()(org)


def test_revoked_seats_do_not_count_against_capacity():
	"""Test VSeatCapacityAvailable only counts active seats, not revoked ones"""

	with step("Arrange: An org with one revoked seat and a limit of one."):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="revoked", username="alice")

	with step("Act: Call VSeatCapacityAvailable."):
		result = VSeatCapacityAvailable()(org)

	with step("Assert: Capacity is still available."):
		assert result is org
