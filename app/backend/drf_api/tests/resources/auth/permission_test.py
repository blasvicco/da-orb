"""This module contains tests for the auth resource permissions"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization
from drf_api.resources.auth.helpers import set_org_admin
from drf_api.resources.auth.permission import PIsOrgAdmin

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def _make_request(headers, org_slug):
	"""Build a lightweight request stand-in exposing .headers and .get_org_slug()"""
	return SimpleNamespace(get_org_slug=lambda: org_slug, headers=headers)


def test_has_permission_organization_not_found():
	"""Test PIsOrgAdmin denies when the org slug does not resolve"""

	with step("Arrange: A request scoped to an unknown slug."):
		request = _make_request({"X-SAP-Username": "bob"}, org_slug="does-not-exist")

	with step("Act: Call has_permission."):
		result = PIsOrgAdmin().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_permission_no_username_resolved():
	"""Test PIsOrgAdmin denies when the request carries no identity header"""

	with step("Arrange: A resolvable org but no X-SAP-Username header."):
		org = _make_org()
		request = _make_request({}, org_slug=org.slug)

	with step("Act: Call has_permission."):
		result = PIsOrgAdmin().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_permission_non_admin_denied():
	"""Test PIsOrgAdmin denies a resolved identity that is not an org admin"""

	with step("Arrange: A resolvable org and a username with no admin grant."):
		org = _make_org()
		request = _make_request({"X-SAP-Username": "bob"}, org_slug=org.slug)

	with step("Act: Call has_permission."):
		result = PIsOrgAdmin().has_permission(request, None)

	with step("Assert: Denied."):
		assert result is False


def test_has_permission_admin_allowed():
	"""Test PIsOrgAdmin allows a resolved identity that holds the org-admin role"""

	with step("Arrange: A resolvable org and a username granted admin."):
		org = _make_org()
		set_org_admin(org, "bob", True)
		request = _make_request({"X-SAP-Username": "bob"}, org_slug=org.slug)

	with step("Act: Call has_permission."):
		result = PIsOrgAdmin().has_permission(request, None)

	with step("Assert: Allowed."):
		assert result is True
