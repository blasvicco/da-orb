"""This module contains tests for the MUsageEvent model"""

# Lib imports
import pytest
from allure import step
from django.utils import timezone

# App imports
from drf_api.models import MChatSession, MOrganization, MUsageEvent

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_str():
	"""Test __str__ returns a non-empty string"""

	with step("Arrange: A persisted usage event."):
		org = _make_org()
		event = MUsageEvent.objects.create(
			event_type="process_execution",
			occurred_on=timezone.now(),
			org=org,
			username="bob",
		)

	with step("Assert: __str__ returns a non-empty string."):
		assert isinstance(str(event), str)
		assert len(str(event)) > 0


def test_survives_session_deletion():
	"""Test deleting the linked chat session sets session to null instead of cascading the deletion"""

	with step("Arrange: A usage event linked to a chat session."):
		org = _make_org()
		session = MChatSession.objects.create(org=org, username="bob")
		event = MUsageEvent.objects.create(
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			session=session,
			total_tokens=10,
			username="bob",
		)

	with step("Act: Delete the chat session."):
		session.delete()

	with step("Assert: The usage event still exists, with session set to null."):
		event.refresh_from_db()
		assert event.session_id is None
		assert event.total_tokens == 10
