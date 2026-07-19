"""This module contains tests for the chat resource permissions"""

# General imports
from types import SimpleNamespace
from unittest.mock import MagicMock

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.resources.chat.permission import PChat


def _make_request(headers=None, method="GET"):
	"""Build a lightweight request stand-in exposing .method and .headers"""
	return SimpleNamespace(headers=headers or {}, method=method)


def _make_view(connection_key, username):
	"""Build a view stand-in whose _get_org_and_user resolves to the given identity"""
	return MagicMock(
		_get_org_and_user=MagicMock(return_value=(None, username, connection_key))
	)


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
		request = _make_request(headers={"Authorization": payload["authorization"]})

	with step("Act: Call has_permission."):
		result = PChat().has_permission(request, None)

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
def test_has_permission_seat_check(payload):
	"""Test has_permission requires a resolved identity holding an active seat"""

	with step(f"Arrange: {payload['description']}."):
		request = _make_request(headers={"Authorization": "Bearer sometoken"})
		org = (
			MOrganization.objects.create(name="acme", slug="acme")
			if payload["has_org"]
			else None
		)
		if payload["has_seat"]:
			MSeat.objects.create(org=org, status="active", username=payload["username"])
		view = MagicMock(
			_get_org_and_user=MagicMock(
				return_value=(org, payload["username"], "TESTDB")
			)
		)

	with step("Act: Call has_permission."):
		result = PChat().has_permission(request, view)

	with step("Assert: Result matches expectation."):
		assert result is payload["expected"]


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "matching username and connection_key is allowed",
			"expected": True,
			"method": "DELETE",
			"obj_connection_key": "TESTDB",
			"obj_username": "bob",
			"resolved_connection_key": "TESTDB",
			"resolved_username": "bob",
		},
		{
			"description": "mismatched connection_key is denied",
			"expected": False,
			"method": "DELETE",
			"obj_connection_key": "TESTDB",
			"obj_username": "bob",
			"resolved_connection_key": "OTHERDB",
			"resolved_username": "bob",
		},
		{
			"description": "mismatched username is denied",
			"expected": False,
			"method": "PATCH",
			"obj_connection_key": "TESTDB",
			"obj_username": "bob",
			"resolved_connection_key": "TESTDB",
			"resolved_username": "alice",
		},
		{
			"description": "unresolved identity (e.g. invalid/expired token) is denied",
			"expected": False,
			"method": "PUT",
			"obj_connection_key": "TESTDB",
			"obj_username": "bob",
			"resolved_connection_key": "TESTDB",
			"resolved_username": "",
		},
		{
			"description": "non-destructive method is always allowed",
			"expected": True,
			"method": "GET",
			"obj_connection_key": "TESTDB",
			"obj_username": "bob",
			"resolved_connection_key": "OTHERDB",
			"resolved_username": "alice",
		},
	],
)
def test_has_object_permission(payload):
	"""Test has_object_permission enforces username and connection_key ownership on destructive verbs."""
	# Resolved via view._get_org_and_user() rather than trusted directly from request headers.

	with step(f"Arrange: {payload['description']}."):
		request = _make_request(method=payload["method"])
		view = _make_view(
			payload["resolved_connection_key"], payload["resolved_username"]
		)
		obj = SimpleNamespace(
			connection_key=payload["obj_connection_key"],
			username=payload["obj_username"],
		)

	with step("Act: Call has_object_permission."):
		result = PChat().has_object_permission(request, view, obj)

	with step("Assert: Result matches expectation."):
		assert result is payload["expected"]
