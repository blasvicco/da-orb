"""This module contains tests for the named-seat licensing helpers"""

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.resources.auth.helpers import (
	has_active_seat,
	provision_or_check_seat,
	reinstate_seat,
)

pytestmark = pytest.mark.django_db


def _make_org(seat_limit=1, slug="acme"):
	"""Create a persisted MOrganization instance with the given seat_limit"""
	return MOrganization.objects.create(name=slug, seat_limit=seat_limit, slug=slug)


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "active seat exists",
			"expected": True,
			"status": "active",
		},
		{
			"description": "revoked seat exists",
			"expected": False,
			"status": "revoked",
		},
		{
			"description": "no seat exists",
			"expected": False,
			"status": None,
		},
	],
)
def test_has_active_seat(payload):
	"""Test has_active_seat only returns True for a row with status='active'"""

	with step(f"Arrange: {payload['description']}."):
		org = _make_org()
		if payload["status"]:
			MSeat.objects.create(org=org, status=payload["status"], username="bob")

	with step("Act: Call has_active_seat."):
		result = has_active_seat(org, "bob")

	with step("Assert: Result matches expectation."):
		assert result is payload["expected"]


def test_provision_or_check_seat_creates_new_seat_when_capacity_allows():
	"""Test provision_or_check_seat creates an active seat when capacity is available"""

	with step("Arrange: An org with capacity for one seat and no existing seats."):
		org = _make_org(seat_limit=1)

	with step("Act: Call provision_or_check_seat for a brand-new username."):
		seat = provision_or_check_seat(org, "bob")

	with step("Assert: A new active seat was created."):
		assert seat.status == "active"
		assert seat.username == "bob"
		assert MSeat.objects.filter(org=org, username="bob", status="active").exists()


def test_provision_or_check_seat_rejects_when_limit_exceeded():
	"""Test provision_or_check_seat raises SEAT_LIMIT_EXCEEDED once the org is at capacity"""

	with step("Arrange: An org with zero remaining capacity."):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="active", username="alice")

	with step("Act/Assert: provision_or_check_seat raises SEAT_LIMIT_EXCEEDED."):
		with pytest.raises(ValidationError, match="SEAT_LIMIT_EXCEEDED"):
			provision_or_check_seat(org, "bob")

	with step("Assert: No row was created for bob."):
		assert not MSeat.objects.filter(org=org, username="bob").exists()


def test_provision_or_check_seat_returns_existing_active_seat():
	"""Test provision_or_check_seat returns the existing row for an already-provisioned username."""
	# Without re-checking capacity — a returning user should never be blocked by a since-lowered limit.

	with step(
		"Arrange: An org already at capacity, with an existing active seat for bob."
	):
		org = _make_org(seat_limit=1)
		existing = MSeat.objects.create(org=org, status="active", username="bob")

	with step("Act: Call provision_or_check_seat for the same username again."):
		seat = provision_or_check_seat(org, "bob")

	with step("Assert: The existing seat is returned."):
		assert seat.id == existing.id


def test_provision_or_check_seat_rejects_revoked_seat():
	"""Test provision_or_check_seat raises SEAT_REVOKED for a username whose seat was revoked"""

	with step("Arrange: An org with a revoked seat for bob."):
		org = _make_org(seat_limit=5)
		MSeat.objects.create(org=org, status="revoked", username="bob")

	with step("Act/Assert: provision_or_check_seat raises SEAT_REVOKED."):
		with pytest.raises(ValidationError, match="SEAT_REVOKED"):
			provision_or_check_seat(org, "bob")


def test_reinstate_seat_rejects_when_seat_not_found():
	"""Test reinstate_seat raises SEAT_NOT_FOUND when no seat row exists for the username"""

	with step("Arrange: An org with no seat for bob."):
		org = _make_org(seat_limit=5)

	with step("Act/Assert: reinstate_seat raises SEAT_NOT_FOUND."):
		with pytest.raises(ValidationError, match="SEAT_NOT_FOUND"):
			reinstate_seat(org, "bob")


def test_reinstate_seat_returns_already_active_seat_unchanged():
	"""Test reinstate_seat is a no-op (no capacity re-check) when the seat is already active"""

	with step("Arrange: An org at capacity, with an already-active seat for bob."):
		org = _make_org(seat_limit=1)
		existing = MSeat.objects.create(org=org, status="active", username="bob")

	with step("Act: Call reinstate_seat on the already-active seat."):
		seat = reinstate_seat(org, "bob")

	with step("Assert: The same seat is returned, still active."):
		assert seat.id == existing.id
		assert seat.status == "active"


def test_reinstate_seat_reactivates_when_capacity_allows():
	"""Test reinstate_seat flips a revoked seat back to active and clears revocation fields"""

	with step("Arrange: An org with capacity and a revoked seat for bob."):
		org = _make_org(seat_limit=5)
		MSeat.objects.create(
			org=org, revoked_by="admin", status="revoked", username="bob"
		)

	with step("Act: Call reinstate_seat."):
		seat = reinstate_seat(org, "bob")

	with step("Assert: The seat is active again with revocation fields cleared."):
		assert seat.status == "active"
		assert seat.revoked_by == ""
		assert seat.revoked_on is None


def test_reinstate_seat_rejects_when_over_capacity():
	"""Test reinstate_seat raises SEAT_LIMIT_EXCEEDED when the org has no capacity left"""

	with step("Arrange: An org at capacity plus a revoked seat for bob."):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="active", username="alice")
		MSeat.objects.create(org=org, status="revoked", username="bob")

	with step("Act/Assert: reinstate_seat raises SEAT_LIMIT_EXCEEDED."):
		with pytest.raises(ValidationError, match="SEAT_LIMIT_EXCEEDED"):
			reinstate_seat(org, "bob")

	with step("Assert: bob's seat stays revoked."):
		assert MSeat.objects.get(org=org, username="bob").status == "revoked"
