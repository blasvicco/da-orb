"""This module contains tests for the seat/role management viewset"""

# Lib imports
import pytest
from allure import step
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.resources.auth.helpers import is_org_admin, set_org_admin
from drf_api.resources.seat.main import VSSeat

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(seat_limit=5, slug="acme"):
	"""Create a persisted MOrganization instance with an admin user ('admin') already granted"""
	org = MOrganization.objects.create(name=slug, seat_limit=seat_limit, slug=slug)
	MSeat.objects.create(org=org, status="active", username="admin")
	set_org_admin(org, "admin", True)
	return org


def _make_request(method, org, data=None, username="admin"):
	"""Build a DRF-compatible request acting as the given (by default, admin) username"""
	build = getattr(_factory, method)
	kwargs = {"data": data, "format": "json"} if data is not None else {}
	request = build("/", HTTP_X_SAP_USERNAME=username, **kwargs)
	request.get_org_slug = lambda: org.slug
	return request


def test_seats_requires_admin():
	"""Test seats denies a non-admin requester"""

	with step("Arrange: A non-admin username."):
		org = _make_org()
		request = _make_request("get", org, username="not-an-admin")

	with step("Act: Call seats."):
		response = VSSeat.as_view({"get": "seats"})(request)

	with step("Assert: 403 is returned."):
		assert response.status_code == 403


def test_seats_lists_org_seats_with_role():
	"""Test seats returns every seat for the org, each annotated with its current role"""

	with step("Arrange: An org with the bootstrap admin plus one standard seat."):
		org = _make_org()
		MSeat.objects.create(org=org, status="active", username="bob")
		request = _make_request("get", org)

	with step("Act: Call seats."):
		response = VSSeat.as_view({"get": "seats"})(request)

	with step("Assert: Both seats are returned with correct roles."):
		assert response.status_code == 200
		by_username = {row["username"]: row["role"] for row in response.data}
		assert by_username == {"admin": "admin", "bob": "standard"}


def test_revoke_marks_seat_revoked_and_records_acting_admin():
	"""Test revoke flips the seat to revoked and records the acting admin as revoked_by"""

	with step("Arrange: An org with a standard seat for bob."):
		org = _make_org()
		MSeat.objects.create(org=org, status="active", username="bob")
		request = _make_request("post", org, data={"username": "bob"})

	with step("Act: Call revoke."):
		response = VSSeat.as_view({"post": "revoke"})(request)

	with step("Assert: The seat is revoked and attributed to the acting admin."):
		assert response.status_code == 200
		seat = MSeat.objects.get(org=org, username="bob")
		assert seat.status == "revoked"
		assert seat.revoked_by == "admin"
		assert seat.revoked_on is not None


def test_revoke_missing_username_returns_400():
	"""Test revoke returns 400 when no target username is given"""

	with step("Arrange: An org, no username in the request body."):
		org = _make_org()
		request = _make_request("post", org, data={})

	with step("Act: Call revoke."):
		response = VSSeat.as_view({"post": "revoke"})(request)

	with step("Assert: 400 is returned."):
		assert response.status_code == 400


def test_revoke_rejects_self():
	"""Test revoke returns 403 when the acting admin targets their own seat"""

	with step("Arrange: An org where the acting admin targets themself."):
		org = _make_org()
		request = _make_request("post", org, data={"username": "admin"})

	with step("Act: Call revoke."):
		response = VSSeat.as_view({"post": "revoke"})(request)

	with step("Assert: 403 CANNOT_REVOKE_SELF and the seat stays active."):
		assert response.status_code == 403
		assert response.data == {"error": "CANNOT_REVOKE_SELF"}
		assert MSeat.objects.get(org=org, username="admin").status == "active"


def test_reinstate_missing_username_returns_400():
	"""Test reinstate returns 400 when no target username is given"""

	with step("Arrange: An org, no username in the request body."):
		org = _make_org()
		request = _make_request("post", org, data={})

	with step("Act: Call reinstate."):
		response = VSSeat.as_view({"post": "reinstate"})(request)

	with step("Assert: 400 MISSING_USERNAME is returned."):
		assert response.status_code == 400
		assert response.data == {"error": "MISSING_USERNAME"}


def test_reinstate_succeeds_within_capacity():
	"""Test reinstate flips a revoked seat back to active when capacity allows"""

	with step("Arrange: An org with capacity and a revoked seat for bob."):
		org = _make_org(seat_limit=5)
		MSeat.objects.create(org=org, status="revoked", username="bob")
		request = _make_request("post", org, data={"username": "bob"})

	with step("Act: Call reinstate."):
		response = VSSeat.as_view({"post": "reinstate"})(request)

	with step("Assert: The seat is active again."):
		assert response.status_code == 200
		assert MSeat.objects.get(org=org, username="bob").status == "active"


def test_reinstate_rejects_when_over_capacity():
	"""Test reinstate returns 403 when the org has no seat capacity left"""

	with step(
		"Arrange: An org at capacity (admin's seat) plus a revoked seat for bob."
	):
		org = _make_org(seat_limit=1)
		MSeat.objects.create(org=org, status="revoked", username="bob")
		request = _make_request("post", org, data={"username": "bob"})

	with step("Act: Call reinstate."):
		response = VSSeat.as_view({"post": "reinstate"})(request)

	with step("Assert: 403 SEAT_LIMIT_EXCEEDED and the seat stays revoked."):
		assert response.status_code == 403
		assert response.data == {"error": "SEAT_LIMIT_EXCEEDED"}
		assert MSeat.objects.get(org=org, username="bob").status == "revoked"


def test_set_role_grants_and_revokes_admin():
	"""Test set_role toggles the org-admin role for the target username"""

	with step("Arrange: An org with a standard seat for bob."):
		org = _make_org()
		MSeat.objects.create(org=org, status="active", username="bob")
		grant_request = _make_request(
			"post", org, data={"role": "admin", "username": "bob"}
		)

	with step("Act: Call set_role to grant admin."):
		response = VSSeat.as_view({"post": "set_role"})(grant_request)

	with step("Assert: bob is now an org admin."):
		assert response.status_code == 200
		assert is_org_admin(org, "bob") is True


def test_set_role_rejects_self_demote():
	"""Test set_role returns 403 when the acting admin tries to remove their own admin access"""

	with step("Arrange: An org where the acting admin targets their own role."):
		org = _make_org()
		request = _make_request(
			"post", org, data={"role": "standard", "username": "admin"}
		)

	with step("Act: Call set_role."):
		response = VSSeat.as_view({"post": "set_role"})(request)

	with step("Assert: 403 CANNOT_REMOVE_OWN_ADMIN and admin keeps the role."):
		assert response.status_code == 403
		assert response.data == {"error": "CANNOT_REMOVE_OWN_ADMIN"}
		assert is_org_admin(org, "admin") is True


def test_set_role_rejects_invalid_role():
	"""Test set_role returns 400 for a role value other than admin/standard"""

	with step("Arrange: An org and an invalid role value."):
		org = _make_org()
		request = _make_request(
			"post", org, data={"role": "superuser", "username": "bob"}
		)

	with step("Act: Call set_role."):
		response = VSSeat.as_view({"post": "set_role"})(request)

	with step("Assert: 400 is returned."):
		assert response.status_code == 400
