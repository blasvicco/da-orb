"""This module contains tests for the request identity resolution helpers"""

# General imports
from datetime import timedelta
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSessionProxy
from drf_api.resources.auth.helpers import resolve_request_identity

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_resolve_request_identity_organization_not_found():
	"""Test resolve_request_identity returns (None, '', '') when the org slug does not resolve"""

	with step("Arrange: A request scoped to an unknown slug."):
		request = SimpleNamespace(
			get_org_slug=lambda: "does-not-exist", headers={"X-SAP-Username": "bob"}
		)

	with step("Act: Call resolve_request_identity."):
		result = resolve_request_identity(request)

	with step("Assert: org is None and username/connection_key are blank."):
		assert result == (None, "", "")


def test_resolve_request_identity_non_b1s_trusts_headers():
	"""Test resolve_request_identity reads username/connection_key straight from headers for non-b1s orgs"""

	with step("Arrange: An open_id org and a request carrying identity headers."):
		org = _make_org()
		request = SimpleNamespace(
			get_org_slug=lambda: org.slug,
			headers={"X-SAP-Connection-Key": "TESTDB", "X-SAP-Username": "bob"},
		)

	with step("Act: Call resolve_request_identity."):
		result = resolve_request_identity(request)

	with step("Assert: Identity matches the request headers."):
		assert result == (org, "bob", "TESTDB")


def test_resolve_request_identity_b1s_ignores_headers_uses_token():
	"""Test resolve_request_identity resolves B1S identity from the verified token, not headers."""
	# Dispatch to the B1S driver happens automatically via FAuthenticator based on org settings.

	with step(
		"Arrange: A b1s org, a live proxy session, and spoofed identity headers."
	):
		org = MOrganization.objects.create(
			integration={
				"auth_driver": "b1s",
				"base_url": "https://fake.example.com/b1s/v1",
			},
			name="acme",
			slug="acme",
		)
		session = MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="live-token",
			username="bob",
		)
		request = SimpleNamespace(
			get_org_slug=lambda: org.slug,
			headers={
				"Authorization": f"Bearer {session.token}",
				"X-SAP-Connection-Key": "SPOOFEDDB",
				"X-SAP-Username": "spoofed-user",
			},
		)

	with step("Act: Call resolve_request_identity."):
		resolved_org, username, connection_key = resolve_request_identity(request)

	with step(
		"Assert: Identity comes from the verified token, ignoring the spoofed headers."
	):
		assert resolved_org.id == org.id
		assert username == "bob"
		assert connection_key == "TESTDB"


def test_resolve_request_identity_b1s_invalid_token():
	"""Test resolve_request_identity returns a blank identity for a b1s org with an unresolvable token"""

	with step("Arrange: A b1s org with no matching proxy session."):
		org = MOrganization.objects.create(
			integration={
				"auth_driver": "b1s",
				"base_url": "https://fake.example.com/b1s/v1",
			},
			name="acme",
			slug="acme",
		)
		request = SimpleNamespace(
			get_org_slug=lambda: org.slug,
			headers={"Authorization": "Bearer does-not-exist"},
		)

	with step("Act: Call resolve_request_identity."):
		result = resolve_request_identity(request)

	with step("Assert: org resolves but username/connection_key are blank."):
		assert result == (org, "", "")
