"""This module contains tests for the OAuth2 WebSocket middleware B1S identity resolution"""

# General imports
from datetime import timedelta

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSeat, MSessionProxy
from web_socket.middleware.oauth2 import get_org_and_user

pytestmark = pytest.mark.django_db(transaction=True)


def _make_org(integration, slug="acme"):
	"""Create a persisted MOrganization instance with the given integration config"""
	return MOrganization.objects.create(integration=integration, name=slug, slug=slug)


def _make_b1s_session(org, expires_delta=timedelta(hours=1)):
	"""Create a persisted MSessionProxy instance for the given org"""
	return MSessionProxy.objects.create(
		auth_driver="b1s",
		connection_key="TESTDB",
		credentials={"password": "secret", "username": "bob"},
		expires_at=timezone.now() + expires_delta,
		org=org,
		token="live-token",
		username="bob",
	)


def test_get_org_and_user_organization_not_found():
	"""Test get_org_and_user returns AnonymousUser when the org slug does not resolve"""

	with step("Act: Call get_org_and_user with an unknown slug."):
		org, user = async_to_sync(get_org_and_user)(
			"does-not-exist",
			{"expires_at": 0, "database": "", "password": ""},
			"sometoken",
		)

	with step("Assert: org is None and the user is anonymous."):
		assert org is None
		assert isinstance(user, AnonymousUser)


def test_get_org_and_user_b1s_valid_token():
	"""Test get_org_and_user resolves a WsUser from a valid B1S opaque token, not query-string fields"""

	with step("Arrange: A b1s org with a live proxy session and an active seat."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		session_proxy = _make_b1s_session(org)
		MSeat.objects.create(org=org, status="active", username="bob")

	with step("Act: Call get_org_and_user with the opaque token."):
		resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug,
			{"expires_at": 0, "database": "", "password": ""},
			session_proxy.token,
			username="someone-else-entirely",
		)

	with step(
		"Assert: Identity is resolved from the token, not the query-string username."
	):
		assert resolved_org.id == org.id
		assert user.is_authenticated
		assert user.username == "bob"
		assert user.session.database == "TESTDB"
		assert user.session.user["password"] == ""


def test_get_org_and_user_b1s_no_active_seat():
	"""Test get_org_and_user returns AnonymousUser for a valid token whose user holds no active seat"""

	with step("Arrange: A b1s org with a live proxy session but no MSeat row."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		session_proxy = _make_b1s_session(org)

	with step("Act: Call get_org_and_user with the opaque token."):
		resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug,
			{"expires_at": 0, "database": "", "password": ""},
			session_proxy.token,
		)

	with step("Assert: org resolves but the user is anonymous."):
		assert resolved_org.id == org.id
		assert isinstance(user, AnonymousUser)


def test_get_org_and_user_b1s_invalid_token():
	"""Test get_org_and_user returns AnonymousUser for a B1S org when the token does not resolve"""

	with step("Arrange: A b1s org with no matching proxy session."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)

	with step("Act: Call get_org_and_user with a bogus token."):
		resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug,
			{"expires_at": 0, "database": "", "password": ""},
			"does-not-exist",
		)

	with step("Assert: org resolves but the user is anonymous."):
		assert resolved_org.id == org.id
		assert isinstance(user, AnonymousUser)
