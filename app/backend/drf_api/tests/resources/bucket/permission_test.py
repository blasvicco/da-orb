"""This module contains tests for the bucket resource permission"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.resources.bucket.permission import PBucket


def _make_request(authorization="Bearer sometoken"):
	"""Build a lightweight request stand-in exposing .headers"""
	return SimpleNamespace(headers={"Authorization": authorization})


@pytest.mark.parametrize(
	"payload",
	[
		{
			"authorization": "Bearer ",
			"description": "empty bearer token is denied",
			"expected": False,
		},
		{
			"authorization": "",
			"description": "missing authorization header is denied",
			"expected": False,
		},
		{
			"authorization": "Basic sometoken",
			"description": "non-bearer scheme is denied",
			"expected": False,
		},
	],
)
def test_has_permission_invalid_bearer_token(payload):
	"""Test has_permission short-circuits to False for a malformed bearer token, before ever resolving identity."""
	# View stays unused, so a None view is safe here.

	with step(f"Arrange: {payload['description']}."):
		request = _make_request(authorization=payload["authorization"])

	with step("Act: Call has_permission."):
		result = PBucket().has_permission(request, None)

	with step("Assert: Result matches expectation."):
		assert result is payload["expected"]


@pytest.mark.django_db
@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "no org resolved is denied",
			"expected": False,
			"has_org": False,
			"has_seat": False,
			"username": "",
		},
		{
			"description": "org resolved but no active seat is denied",
			"expected": False,
			"has_org": True,
			"has_seat": False,
			"username": "bob",
		},
		{
			"description": "org resolved with an active seat is allowed",
			"expected": True,
			"has_org": True,
			"has_seat": True,
			"username": "bob",
		},
	],
)
def test_has_permission_seat_check(mocker, payload):
	"""Test has_permission requires a resolved identity holding an active seat"""

	with step(f"Arrange: {payload['description']}."):
		request = _make_request()
		org = (
			MOrganization.objects.create(name="acme", slug="acme")
			if payload["has_org"]
			else None
		)
		if payload["has_seat"]:
			MSeat.objects.create(org=org, status="active", username=payload["username"])
		mocker.patch(
			"drf_api.resources.seat.permission.resolve_request_identity",
			return_value=(org, payload["username"], "TESTDB"),
		)

	with step("Act: Call has_permission."):
		result = PBucket().has_permission(request, None)

	with step("Assert: Result matches expectation."):
		assert result is payload["expected"]
