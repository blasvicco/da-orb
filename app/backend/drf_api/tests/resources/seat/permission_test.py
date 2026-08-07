"""This module contains tests for the seat resource permissions"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.resources.seat.permission import PHasActiveSeat

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def _make_request(headers, org_slug):
	"""Build a lightweight request stand-in exposing .headers and .get_org_slug()"""
	return SimpleNamespace(get_org_slug=lambda: org_slug, headers=headers)


def test_has_active_seat_denies_without_bearer_token():
	"""Test PHasActiveSeat denies a request with no Bearer token, before resolving identity"""

	with step("Arrange: A request with no Authorization header."):
		request = _make_request({"X-SAP-Username": "bob"}, org_slug="acme")

	with step("Act: Call has_permission."):
		result = PHasActiveSeat().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_active_seat_organization_not_found():
	"""Test PHasActiveSeat denies when the org slug does not resolve"""

	with step("Arrange: A request scoped to an unknown slug."):
		request = _make_request(
			{"Authorization": "Bearer sometoken", "X-SAP-Username": "bob"},
			org_slug="does-not-exist",
		)

	with step("Act: Call has_permission."):
		result = PHasActiveSeat().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_active_seat_no_seat_denied():
	"""Test PHasActiveSeat denies a resolved identity with no active seat"""

	with step("Arrange: A resolvable org/username but no MSeat row."):
		org = _make_org()
		request = _make_request(
			{"Authorization": "Bearer sometoken", "X-SAP-Username": "bob"},
			org_slug=org.slug,
		)

	with step("Act: Call has_permission."):
		result = PHasActiveSeat().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_active_seat_allowed():
	"""Test PHasActiveSeat allows a resolved identity holding an active seat"""

	with step("Arrange: A resolvable org/username with an active seat."):
		org = _make_org()
		MSeat.objects.create(org=org, status="active", username="bob")
		request = _make_request(
			{"Authorization": "Bearer sometoken", "X-SAP-Username": "bob"},
			org_slug=org.slug,
		)

	with step("Act: Call has_permission."):
		result = PHasActiveSeat().has_permission(request, None)

	with step("Assert: Allowed."):
		assert result is True
