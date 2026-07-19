"""This module contains tests for the MSessionProxy model"""

# Lib imports
import pytest
from allure import step
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSessionProxy

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_issue_persists_encrypted_credentials():
	"""Test issue creates a row with a unique token and the given credentials/connection_key"""

	with step("Arrange: An organization to attach the proxy session to."):
		org = _make_org()

	with step("Act: Call issue."):
		session = MSessionProxy.issue(
			auth_driver="b1s",
			connection_key="TESTDB",
			org=org,
			password="secret",
			username="bob",
		)

	with step("Assert: The row was persisted with the expected shape."):
		assert session.auth_driver == "b1s"
		assert session.connection_key == "TESTDB"
		assert session.credentials == {"password": "secret", "username": "bob"}
		assert session.expires_at > timezone.now()
		assert len(session.token) > 20


def test_issue_generates_distinct_tokens():
	"""Test issue mints a different opaque token on every call"""

	with step("Arrange: An organization to attach two proxy sessions to."):
		org = _make_org()

	with step("Act: Call issue twice for the same identity."):
		first = MSessionProxy.issue(
			auth_driver="b1s",
			connection_key="TESTDB",
			org=org,
			password="secret",
			username="bob",
		)
		second = MSessionProxy.issue(
			auth_driver="b1s",
			connection_key="TESTDB",
			org=org,
			password="secret",
			username="bob",
		)

	with step(
		"Assert: Two distinct rows/tokens exist — concurrent sessions are allowed."
	):
		assert first.token != second.token
		assert MSessionProxy.objects.filter(org=org, username="bob").count() == 2


def test_str():
	"""Test __str__ returns a non-empty string"""

	with step("Arrange: A persisted proxy session."):
		session = MSessionProxy.issue(
			auth_driver="b1s",
			connection_key="TESTDB",
			org=_make_org(),
			password="secret",
			username="bob",
		)

	with step("Assert: __str__ returns a non-empty string."):
		assert isinstance(str(session), str)
		assert len(str(session)) > 0
