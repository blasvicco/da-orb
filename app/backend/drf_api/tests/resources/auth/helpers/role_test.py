"""This module contains tests for the Django Group-backed org-admin role helpers"""

# Lib imports
import pytest
from allure import step
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

# App imports
from drf_api.models import MOrganization
from drf_api.resources.auth.helpers import (
	get_org_admin_group,
	is_org_admin,
	set_org_admin,
)

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_get_org_admin_group_is_idempotent():
	"""Test get_org_admin_group returns the same row on repeated calls, namespaced per org"""

	with step("Arrange: Two distinct orgs."):
		org_a = _make_org(slug="acme")
		org_b = _make_org(slug="globex")

	with step("Act: Call get_org_admin_group twice for org_a, once for org_b."):
		first = get_org_admin_group(org_a)
		second = get_org_admin_group(org_a)
		other = get_org_admin_group(org_b)

	with step("Assert: Same group for repeated calls, distinct group per org."):
		assert first.id == second.id
		assert first.name == "org-admin:acme"
		assert other.id != first.id
		assert other.name == "org-admin:globex"


def test_is_org_admin_false_by_default():
	"""Test is_org_admin returns False for a username that was never granted the role"""

	with step("Arrange: An org and a username with no peg user at all."):
		org = _make_org()

	with step("Act: Call is_org_admin."):
		result = is_org_admin(org, "bob")

	with step("Assert: False."):
		assert result is False


def test_set_org_admin_grants_and_revokes():
	"""Test set_org_admin adds/removes the peg user's membership in the org's admin group"""

	with step("Arrange: An org and a username."):
		org = _make_org()

	with step("Act: Grant admin, then check."):
		set_org_admin(org, "bob", True)
		granted = is_org_admin(org, "bob")

	with step("Act: Revoke admin, then check."):
		set_org_admin(org, "bob", False)
		revoked = is_org_admin(org, "bob")

	with step("Assert: Role reflected correctly at each step."):
		assert granted is True
		assert revoked is False


def test_set_org_admin_peg_user_is_not_login_capable():
	"""Test the peg user created by set_org_admin cannot authenticate anywhere"""

	with step("Arrange: An org and a username."):
		org = _make_org()

	with step("Act: Grant admin, creating the peg user."):
		set_org_admin(org, "bob", True)

	with step(
		"Assert: The peg user is namespaced, has no usable password, and is not staff."
	):
		user = get_user_model().objects.get(username="acme.bob")
		assert user.has_usable_password() is False
		assert user.is_staff is False


def test_set_org_admin_namespaces_by_org():
	"""Test the same SAP username in two different orgs maps to two distinct peg users"""

	with step("Arrange: Two orgs, same SAP username granted admin in only one."):
		org_a = _make_org(slug="acme")
		org_b = _make_org(slug="globex")

	with step("Act: Grant admin for bob in org_a only."):
		set_org_admin(org_a, "bob", True)

	with step("Assert: bob is admin in org_a but not in org_b."):
		assert is_org_admin(org_a, "bob") is True
		assert is_org_admin(org_b, "bob") is False


def test_set_org_admin_does_not_create_duplicate_group_rows():
	"""Test granting admin to two usernames in the same org reuses a single Group row"""

	with step("Arrange: An org."):
		org = _make_org()

	with step("Act: Grant admin to two different usernames."):
		set_org_admin(org, "bob", True)
		set_org_admin(org, "alice", True)

	with step("Assert: Exactly one Group row exists for this org."):
		assert Group.objects.filter(name="org-admin:acme").count() == 1
