"""This module contains tests for the custom Django admin registrations"""

# General imports
import json
from unittest.mock import MagicMock

# Lib imports
import pytest
from allure import step
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.http import HttpResponseRedirect

# App imports
from drf_api.admin import (
	MOrganizationAdmin,
	MOrganizationForm,
	MSeatAdmin,
	MSessionProxyAdmin,
)
from drf_api.models import MSeat, MSessionProxy
from drf_api.resources.auth.helpers import is_org_admin, set_org_admin
from drf_api.tests.factories import FOrganization, FSeat

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# MOrganizationForm.__init__
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "dict integration is re-serialised as pretty JSON",
			"expected_contains": '"auth_driver": "b1s"',
			"integration": {"auth_driver": "b1s"},
		},
		{
			"description": "valid JSON string integration is parsed and re-serialised",
			"expected_contains": '"auth_driver": "b1s"',
			"integration": '{"auth_driver": "b1s"}',
		},
		{
			"description": "invalid JSON string integration falls back to the raw string",
			"expected_contains": "not-json",
			"integration": "not-json",
		},
	],
)
def test_form_init_prepopulates_integration_field(payload):
	"""Test MOrganizationForm.__init__ renders the instance's integration value as initial data"""

	with step(f"Arrange: {payload['description']}."):
		org = FOrganization.build(integration=payload["integration"])

	with step("Act: Instantiate the form bound to the org."):
		form = MOrganizationForm(instance=org)

	with step("Assert: The initial integration value contains the expected text."):
		assert payload["expected_contains"] in form.initial["integration"]


# ---------------------------------------------------------------------------
# MOrganizationForm.clean_integration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "empty integration returns an empty dict",
			"expected": {},
			"integration": "",
			"valid": True,
		},
		{
			"description": "valid open_id config with all required keys",
			"expected": {
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			},
			"integration": json.dumps(
				{
					"auth_driver": "open_id",
					"base_url": "https://sap.example.com",
					"client_id": "id",
					"client_secret": "secret",
				}
			),
			"valid": True,
		},
		{
			"description": "invalid JSON string",
			"error": "Invalid JSON format",
			"integration": "{not json",
			"valid": False,
		},
		{
			"description": "JSON that is not an object",
			"error": "JSON object",
			"integration": json.dumps(["a", "b"]),
			"valid": False,
		},
		{
			"description": "missing auth_driver key",
			"error": "Missing required key",
			"integration": json.dumps({"base_url": "https://sap.example.com"}),
			"valid": False,
		},
		{
			"description": "unknown auth_driver",
			"error": "Unknown auth_driver",
			"integration": json.dumps({"auth_driver": "unknown"}),
			"valid": False,
		},
		{
			"description": "known driver missing required keys",
			"error": "Missing required integration keys",
			"integration": json.dumps({"auth_driver": "b1s"}),
			"valid": False,
		},
	],
)
def test_clean_integration(payload):
	"""Test MOrganizationForm.clean_integration validates the submitted JSON per auth driver"""

	with step(f"Arrange: {payload['description']}."):
		form = MOrganizationForm(
			data={
				"integration": payload["integration"],
				"name": "Acme",
				"seat_limit": "0",
				"slug": "acme-clean-integration",
			}
		)

	with step("Act: Validate the form."):
		is_valid = form.is_valid()

	with step("Assert: Outcome matches expected."):
		if payload["valid"]:
			assert is_valid
			assert form.cleaned_data["integration"] == payload["expected"]
		else:
			assert not is_valid
			assert payload["error"] in str(form.errors["integration"])


# ---------------------------------------------------------------------------
# MOrganizationAdmin.get_auth_driver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "no configured driver defaults to open_id",
			"expected": "open_id",
			"integration": {},
		},
		{
			"description": "configured driver is returned as-is",
			"expected": "b1s",
			"integration": {"auth_driver": "b1s"},
		},
	],
)
def test_get_auth_driver(payload):
	"""Test MOrganizationAdmin.get_auth_driver reads the configured driver, defaulting to open_id"""

	with step(f"Arrange: {payload['description']}."):
		org = FOrganization.create(integration=payload["integration"])
		admin_instance = MOrganizationAdmin(org.__class__, AdminSite())

	with step("Act: Call get_auth_driver."):
		result = admin_instance.get_auth_driver(org)

	with step("Assert: The expected driver is returned."):
		assert result == payload["expected"]


# ---------------------------------------------------------------------------
# MSessionProxyAdmin
# ---------------------------------------------------------------------------


def test_session_proxy_admin_disallows_add_and_change():
	"""Test MSessionProxyAdmin denies both add and change permissions unconditionally"""

	with step("Arrange: A session proxy admin instance."):
		admin_instance = MSessionProxyAdmin(MSessionProxy, AdminSite())
		request = MagicMock()

	with step("Act: Call has_add_permission and has_change_permission."):
		can_add = admin_instance.has_add_permission(request)
		can_change = admin_instance.has_change_permission(request)

	with step("Assert: Both are denied."):
		assert can_add is False
		assert can_change is False


# ---------------------------------------------------------------------------
# MSeatAdmin.get_role
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "admin seat", "expected": "Admin", "is_admin": True},
		{"description": "standard seat", "expected": "Standard", "is_admin": False},
	],
)
def test_get_role(payload):
	"""Test MSeatAdmin.get_role labels the seat according to its org-admin status"""

	with step(f"Arrange: {payload['description']}."):
		org = FOrganization.create()
		seat = FSeat.create(org=org, username="bob")
		if payload["is_admin"]:
			set_org_admin(org, "bob", True)
		admin_instance = MSeatAdmin(MSeat, AdminSite())

	with step("Act: Call get_role."):
		result = admin_instance.get_role(seat)

	with step("Assert: The expected label is returned."):
		assert result == payload["expected"]


# ---------------------------------------------------------------------------
# MSeatAdmin.change_view
# ---------------------------------------------------------------------------


def test_change_view_injects_seat_is_admin_when_seat_exists(mocker):
	"""Test MSeatAdmin.change_view injects seat_is_admin into extra_context when the seat is found"""

	with step("Arrange: An admin seat and a mocked parent change_view."):
		org = FOrganization.create()
		seat = FSeat.create(org=org, username="bob")
		set_org_admin(org, "bob", True)
		admin_instance = MSeatAdmin(MSeat, AdminSite())
		super_change_view = mocker.patch.object(
			admin.ModelAdmin, "change_view", return_value="rendered"
		)
		request = MagicMock()

	with step("Act: Call change_view."):
		result = admin_instance.change_view(request, str(seat.id))

	with step(
		"Assert: extra_context carries seat_is_admin=True, response passed through."
	):
		assert result == "rendered"
		called_args = super_change_view.call_args.args
		assert called_args[3]["seat_is_admin"] is True


def test_change_view_when_seat_not_found(mocker):
	"""Test MSeatAdmin.change_view leaves extra_context untouched when the seat can't be resolved"""

	with step(
		"Arrange: An admin instance, a non-existent object id, and a mocked parent."
	):
		admin_instance = MSeatAdmin(MSeat, AdminSite())
		super_change_view = mocker.patch.object(
			admin.ModelAdmin, "change_view", return_value="rendered"
		)
		request = MagicMock()

	with step("Act: Call change_view for an unknown id."):
		result = admin_instance.change_view(request, "999999")

	with step("Assert: extra_context stays empty, response passed through."):
		assert result == "rendered"
		called_args = super_change_view.call_args.args
		assert "seat_is_admin" not in called_args[3]


# ---------------------------------------------------------------------------
# MSeatAdmin.response_change
# ---------------------------------------------------------------------------


def test_response_change_toggles_role_when_requested(mocker):
	"""Test MSeatAdmin.response_change toggles the seat's org-admin role and redirects"""

	with step("Arrange: A standard seat and a POST carrying the toggle flag."):
		org = FOrganization.create()
		seat = FSeat.create(org=org, username="bob")
		admin_instance = MSeatAdmin(MSeat, AdminSite())
		message_user = mocker.patch.object(admin_instance, "message_user")
		request = MagicMock(
			POST={"_toggle_role": "1"}, path="/admin/drf_api/mseat/1/change/"
		)

	with step("Act: Call response_change."):
		result = admin_instance.response_change(request, seat)

	with step("Assert: The role was toggled on and a redirect was returned."):
		assert isinstance(result, HttpResponseRedirect)
		assert is_org_admin(org, "bob") is True
		message_user.assert_called_once()


def test_response_change_falls_through_without_toggle(mocker):
	"""Test MSeatAdmin.response_change defers to the default behaviour without the toggle flag"""

	with step("Arrange: A seat and a POST without the toggle flag."):
		org = FOrganization.create()
		seat = FSeat.create(org=org, username="bob")
		admin_instance = MSeatAdmin(MSeat, AdminSite())
		super_response_change = mocker.patch.object(
			admin.ModelAdmin, "response_change", return_value="fallback"
		)
		request = MagicMock(POST={})

	with step("Act: Call response_change."):
		result = admin_instance.response_change(request, seat)

	with step("Assert: The default ModelAdmin behaviour was used."):
		assert result == "fallback"
		super_response_change.assert_called_once()
