"""This module contains tests for the OAuth2 WebSocket middleware B1S identity resolution"""

# General imports
import base64
import json
import time
from datetime import timedelta
from unittest.mock import AsyncMock

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSeat, MSessionProxy
from web_socket.middleware.oauth2 import MOAuth2, get_org_and_user

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


def test_get_org_and_user_no_token():
	"""Test get_org_and_user returns AnonymousUser when no token is given, even for a resolvable org"""

	with step("Arrange: A resolvable org."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)

	with step("Act: Call get_org_and_user with an empty token."):
		resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug, {"expires_at": 0, "database": "", "password": ""}, ""
		)

	with step("Assert: org resolves but the user is anonymous."):
		assert resolved_org.id == org.id
		assert isinstance(user, AnonymousUser)


def test_get_org_and_user_unknown_auth_driver():
	"""Test get_org_and_user returns AnonymousUser when the org's auth_driver isn't registered"""

	with step("Arrange: An org configured with an unknown auth_driver."):
		org = _make_org({"auth_driver": "not-a-real-driver"})

	with step("Act: Call get_org_and_user with any token."):
		resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug, {"expires_at": 0, "database": "", "password": ""}, "sometoken"
		)

	with step("Assert: org resolves but the user is anonymous."):
		assert resolved_org.id == org.id
		assert isinstance(user, AnonymousUser)


def test_ws_user_to_dict_delegates_to_session():
	"""Test WsUser.to_dict() delegates to the wrapped MSession's to_dict()"""

	with step("Arrange: A resolved WsUser from a valid B1S opaque token."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		session_proxy = _make_b1s_session(org)
		MSeat.objects.create(org=org, status="active", username="bob")

	with step("Act: Resolve the user and call to_dict()."):
		_resolved_org, user = async_to_sync(get_org_and_user)(
			org.slug,
			{"expires_at": 0, "database": "", "password": ""},
			session_proxy.token,
		)
		result = user.to_dict()

	with step("Assert: The result matches the wrapped session's to_dict()."):
		assert result == user.session.to_dict()


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


# ---------------------------------------------------------------------------
# MOAuth2 middleware
# ---------------------------------------------------------------------------


def test_call_resolves_organization_and_user_with_valid_token():
	"""Test MOAuth2.__call__ resolves organization/user into scope and delegates to inner"""

	with step("Arrange: A b1s org with a live proxy session and an active seat."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		session_proxy = _make_b1s_session(org)
		MSeat.objects.create(org=org, status="active", username="bob")
		inner = AsyncMock(return_value="inner-result")
		middleware = MOAuth2(inner)
		scope = {
			"headers": [(b"host", f"{org.slug}.orb.test".encode())],
			"query_string": f"token={session_proxy.token}".encode(),
		}

	with step("Act: Call the middleware."):
		result = async_to_sync(middleware)(scope, None, None)

	with step("Assert: scope carries the resolved org/user and inner was awaited."):
		assert result == "inner-result"
		assert scope["organization"].id == org.id
		assert scope["user"].username == "bob"
		inner.assert_awaited_once_with(scope, None, None)


def test_call_skips_resolution_without_token():
	"""Test MOAuth2.__call__ leaves scope anonymous when no token is in the query string"""

	with step("Arrange: A scope with a resolvable host but no token."):
		inner = AsyncMock(return_value="inner-result")
		middleware = MOAuth2(inner)
		scope = {"headers": [(b"host", b"acme.orb.test")], "query_string": b""}

	with step("Act: Call the middleware."):
		async_to_sync(middleware)(scope, None, None)

	with step("Assert: scope stays anonymous, inner is still called."):
		assert scope["organization"] is None
		assert isinstance(scope["user"], AnonymousUser)
		inner.assert_awaited_once()


def test_call_skips_resolution_without_host_header():
	"""Test MOAuth2.__call__ leaves scope anonymous when there is no Host header to derive an org slug"""

	with step("Arrange: A scope with a token but no Host header."):
		inner = AsyncMock(return_value="inner-result")
		middleware = MOAuth2(inner)
		scope = {"headers": [], "query_string": b"token=sometoken"}

	with step("Act: Call the middleware."):
		async_to_sync(middleware)(scope, None, None)

	with step("Assert: scope stays anonymous, inner is still called."):
		assert scope["organization"] is None
		assert isinstance(scope["user"], AnonymousUser)
		inner.assert_awaited_once()


def test_call_decodes_jwt_expiry_claim(mocker):
	"""Test MOAuth2.__call__ decodes a valid JWT's exp claim into session_data.expires_at"""

	with step("Arrange: A token whose payload carries a future exp claim."):
		mock_get = mocker.patch(
			"web_socket.middleware.oauth2.get_org_and_user",
			AsyncMock(return_value=(None, AnonymousUser())),
		)
		inner = AsyncMock()
		middleware = MOAuth2(inner)
		future_exp = int(time.time()) + 9999
		payload_b64 = (
			base64.urlsafe_b64encode(json.dumps({"exp": future_exp}).encode())
			.decode()
			.rstrip("=")
		)
		token = f"header.{payload_b64}.signature"
		scope = {
			"headers": [(b"host", b"acme.orb.test")],
			"query_string": f"token={token}".encode(),
		}

	with step("Act: Call the middleware."):
		async_to_sync(middleware)(scope, None, None)

	with step("Assert: The decoded exp claim was used as expires_at."):
		sent_session_data = mock_get.call_args.args[1]
		assert sent_session_data["expires_at"] == future_exp


def test_call_falls_back_to_default_expiry_for_a_non_jwt_token(mocker):
	"""Test MOAuth2.__call__ falls back to now + 1800s when the token isn't a decodable JWT"""

	with step("Arrange: An opaque (non-JWT) token."):
		mock_get = mocker.patch(
			"web_socket.middleware.oauth2.get_org_and_user",
			AsyncMock(return_value=(None, AnonymousUser())),
		)
		inner = AsyncMock()
		middleware = MOAuth2(inner)
		scope = {
			"headers": [(b"host", b"acme.orb.test")],
			"query_string": b"token=not-a-jwt-token",
		}

	with step("Act: Call the middleware."):
		before = int(time.time())
		async_to_sync(middleware)(scope, None, None)
		after = int(time.time())

	with step("Assert: expires_at falls back to roughly now + 1800 seconds."):
		sent_session_data = mock_get.call_args.args[1]
		assert before + 1800 <= sent_session_data["expires_at"] <= after + 1800
