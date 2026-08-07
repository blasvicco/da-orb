"""This module contains tests for the seat reactions to auth-domain events"""

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from core.modules.hooks import Hooks
from drf_api.models import MOrganization, MSeat

pytestmark = pytest.mark.django_db


def _make_org(seat_limit=1, slug="acme"):
	"""Create a persisted MOrganization instance with the given seat_limit"""
	return MOrganization.objects.create(name=slug, seat_limit=seat_limit, slug=slug)


def test_seat_registers_provision_or_check_seat_for_user_authenticated():
	"""Test importing the seat resource registers provision_or_check_seat as a user_authenticated listener"""
	# Real registration, not a mock — drf_api/resources/seat/__init__.py's import
	# of receivers.py already ran by the time this test executes.

	with step("Act: Read the registered listeners for user_authenticated."):
		methods = [method for method, _, _ in Hooks.get_listeners("user_authenticated")]

	with step("Assert: provision_or_check_seat is registered."):
		assert MSeat.provision_or_check_seat in methods


def test_firing_user_authenticated_provisions_a_seat():
	"""Test calling every registered user_authenticated listener provisions a seat for a new user"""
	# Matches auth/main.py's own fire convention (iterate Hooks.get_listeners, call each).

	with step("Arrange: An org with capacity and no existing seat for bob."):
		org = _make_org(seat_limit=1)

	with step("Act: Fire user_authenticated the same way auth/main.py does."):
		for method, _, _ in Hooks.get_listeners("user_authenticated"):
			method(org, "bob")

	with step("Assert: A new active seat was created."):
		assert MSeat.objects.filter(org=org, username="bob", status="active").exists()


def test_firing_user_authenticated_propagates_seat_limit_exceeded():
	"""Test firing user_authenticated raises ValidationError when the org is at capacity"""

	with step("Arrange: An org already at capacity."):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="active", username="alice")

	with step("Act/Assert: Firing raises SEAT_LIMIT_EXCEEDED."):
		with pytest.raises(ValidationError, match="SEAT_LIMIT_EXCEEDED"):
			for method, _, _ in Hooks.get_listeners("user_authenticated"):
				method(org, "bob")
