"""This module contains tests for the auth viewset login/callback actions"""

# General imports
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MOrganization, MSessionProxy
from drf_api.resources.auth.driver.abstract import AuthDriverError
from drf_api.resources.auth.main import VSAuth

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(integration, seat_limit=1, slug="acme"):
	"""Create a persisted MOrganization instance with the given integration config"""
	return MOrganization.objects.create(
		integration=integration, name=slug, seat_limit=seat_limit, slug=slug
	)


def _login_request(data, org_slug="acme"):
	"""Build a DRF-compatible POST request scoped to the given org slug"""
	request = _factory.post("/", data, format="json")
	request.get_org_slug = lambda: org_slug
	return request


def test_login_organization_not_found():
	"""Test login returns 404 when the org slug does not resolve"""

	with step("Arrange: A request against a slug with no matching org."):
		request = _login_request(
			{"database": "TESTDB", "password": "secret", "username": "bob"},
			org_slug="does-not-exist",
		)

	with step("Act: Call login."):
		response = VSAuth.as_view({"post": "login"})(request)

	with step("Assert: 404 ORGANIZATION_NOT_FOUND is returned."):
		assert response.status_code == 404
		assert response.data == {"error": "ORGANIZATION_NOT_FOUND"}


def test_login_missing_credentials():
	"""Test login returns 400 when required B1S credentials are absent"""

	with step("Arrange: A b1s org and a request missing the database field."):
		_make_org({"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"})
		request = _login_request({"password": "secret", "username": "bob"})

	with step("Act: Call login."):
		response = VSAuth.as_view({"post": "login"})(request)

	with step("Assert: 400 MISSING_CREDENTIALS is returned."):
		assert response.status_code == 400
		assert response.data == {"error": "MISSING_CREDENTIALS"}


def test_login_open_id_not_supported():
	"""Test login returns 405 for an open_id org, which does not support credential login"""

	with step("Arrange: An open_id org."):
		_make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _login_request({"password": "secret", "username": "bob"})

	with step("Act: Call login."):
		response = VSAuth.as_view({"post": "login"})(request)

	with step("Assert: 405 METHOD_NOT_ALLOWED is returned."):
		assert response.status_code == 405
		assert response.data == {"error": "METHOD_NOT_ALLOWED"}


def test_login_b1s_success_issues_opaque_token():
	"""Test a successful B1S login mints an MSessionProxy and never echoes the raw password back"""

	with step("Arrange: A b1s org and a mocked successful SAP Login response."):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		request = _login_request(
			{"database": "TESTDB", "password": "secret", "username": "bob"}
		)
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"SessionId": "raw-sap-session-id"}

	with step("Act: Call login."):
		with patch(
			"drf_api.resources.auth.driver.b1s.requests.post",
			return_value=mock_response,
		):
			response = VSAuth.as_view({"post": "login"})(request)

	with step(
		"Assert: An opaque token is returned, the password is blank, and a proxy row exists."
	):
		assert response.status_code == 200
		assert response.data["user"]["password"] == ""
		assert response.data["access_token"] != "raw-sap-session-id"

		session_proxy = MSessionProxy.objects.get(org=org, username="bob")
		assert session_proxy.auth_driver == "b1s"
		assert session_proxy.token == response.data["access_token"]
		assert session_proxy.connection_key == "TESTDB"
		assert session_proxy.credentials == {"password": "secret", "username": "bob"}


def test_login_b1s_seat_limit_exceeded():
	"""Test login returns 403 and creates no proxy session when the org has no seat capacity left"""

	with step(
		"Arrange: A b1s org with zero seat capacity and a mocked successful SAP Login."
	):
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"},
			seat_limit=0,
		)
		request = _login_request(
			{"database": "TESTDB", "password": "secret", "username": "bob"}
		)
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"SessionId": "raw-sap-session-id"}

	with step("Act: Call login."):
		with patch(
			"drf_api.resources.auth.driver.b1s.requests.post",
			return_value=mock_response,
		):
			response = VSAuth.as_view({"post": "login"})(request)

	with step(
		"Assert: 403 SEAT_LIMIT_EXCEEDED is returned and no proxy row was created."
	):
		assert response.status_code == 403
		assert response.data == {"error": "SEAT_LIMIT_EXCEEDED"}
		assert not MSessionProxy.objects.filter(org=org, username="bob").exists()


def test_callback_sap_error_redirects_with_error():
	"""Test callback redirects with the SAP-supplied error, before any org/driver lookup"""

	with step("Arrange: A callback request carrying an error_description query param."):
		request = _factory.get("/", {"error_description": "access_denied"})
		request.get_org_slug = lambda: "acme"

	with step("Act: Call callback."):
		response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects with the SAP error in the query string."):
		assert response.status_code == 302
		assert "access_denied" in response.url


def test_callback_missing_code_redirects_with_error():
	"""Test callback redirects with AUTHORIZATION_MISSING_CODE when no code is present"""

	with step("Arrange: A callback request with no code query param."):
		request = _factory.get("/")
		request.get_org_slug = lambda: "acme"

	with step("Act: Call callback."):
		response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects with AUTHORIZATION_MISSING_CODE in the query string."):
		assert response.status_code == 302
		assert "AUTHORIZATION_MISSING_CODE" in response.url


def test_callback_organization_not_found_redirects_with_error():
	"""Test callback redirects with ORGANIZATION_NOT_FOUND when the org slug does not resolve"""

	with step("Arrange: A callback request against a slug with no matching org."):
		request = _factory.get("/", {"code": "authcode"})
		request.get_org_slug = lambda: "does-not-exist"

	with step("Act: Call callback."):
		response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects with ORGANIZATION_NOT_FOUND in the query string."):
		assert response.status_code == 302
		assert "ORGANIZATION_NOT_FOUND" in response.url


def test_callback_driver_error_redirects_with_error():
	"""Test callback redirects with the driver's error message when authenticate() fails"""

	with step("Arrange: An open_id org whose authenticate() call fails."):
		org = _make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _factory.get("/", {"code": "bad-code"})
		request.get_org_slug = lambda: org.slug

	with step("Act: Call callback with authenticate() mocked to raise."):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.authenticate",
			side_effect=AuthDriverError("invalid_grant"),
		):
			response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects with the driver's error message in the query string."):
		assert response.status_code == 302
		assert "invalid_grant" in response.url


def test_callback_invalid_auth_driver_redirects_with_unwrapped_error():
	"""Test callback unwraps a list-shaped ValidationError detail before building the redirect"""

	with step("Arrange: An org configured with an unknown auth_driver."):
		org = _make_org({"auth_driver": "not-a-real-driver"})
		request = _factory.get("/", {"code": "authcode"})
		request.get_org_slug = lambda: org.slug

	with step("Act: Call callback."):
		response = VSAuth.as_view({"get": "callback"})(request)

	with step(
		"Assert: Redirects with the unwrapped error message in the query string."
	):
		assert response.status_code == 302
		assert "NOT_VALID_AUTH_DRIVER" in response.url


def test_callback_seat_limit_exceeded_redirects_with_error():
	"""Test callback redirects with a seat-limit error, without ever reaching the redirect-with-session step"""

	with step(
		"Arrange: An open_id org with zero seat capacity and a mocked successful exchange."
	):
		org = _make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			},
			seat_limit=0,
		)
		request = _factory.get("/", {"code": "authcode"})
		request.get_org_slug = lambda: org.slug

	with step("Act: Call callback with authenticate() mocked to succeed."):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.authenticate",
			return_value={
				"access_token": "tok",
				"database": "",
				"expires_at": 0,
				"id_token": "",
				"org": org.slug,
				"refresh_token": "",
				"user": {"password": "", "username": "bob"},
			},
		):
			response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects with SEAT_LIMIT_EXCEEDED in the query string."):
		assert response.status_code == 302
		assert "SEAT_LIMIT_EXCEEDED" in response.url


def test_callback_success_redirects_with_session():
	"""Test a fully successful callback provisions the seat, sets the role, and redirects with the session"""

	with step(
		"Arrange: An open_id org with seat capacity and a mocked successful exchange."
	):
		org = _make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _factory.get("/", {"code": "authcode"})
		request.get_org_slug = lambda: org.slug

	with step("Act: Call callback with authenticate() mocked to succeed."):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.authenticate",
			return_value={
				"access_token": "tok",
				"database": "",
				"expires_at": 0,
				"id_token": "",
				"org": org.slug,
				"refresh_token": "",
				"user": {"password": "", "username": "bob"},
			},
		):
			response = VSAuth.as_view({"get": "callback"})(request)

	with step("Assert: Redirects to the frontend callback route carrying the session."):
		assert response.status_code == 302
		assert "/auth/callback?session=" in response.url


def test_login_invalid_auth_driver():
	"""Test login returns 400 when the org's configured auth_driver isn't registered"""

	with step("Arrange: An org configured with an unknown auth_driver."):
		_make_org({"auth_driver": "not-a-real-driver"})
		request = _login_request({"password": "secret", "username": "bob"})

	with step("Act: Call login."):
		response = VSAuth.as_view({"post": "login"})(request)

	with step("Assert: 400 NOT_VALID_AUTH_DRIVER is returned."):
		assert response.status_code == 400
		assert response.data == {"error": ["NOT_VALID_AUTH_DRIVER"]}


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


def _refresh_request(data, org_slug="acme"):
	"""Build a DRF-compatible POST request scoped to the given org slug"""
	request = _factory.post("/", data, format="json")
	request.get_org_slug = lambda: org_slug
	return request


def test_refresh_missing_token():
	"""Test refresh returns 400 when the token field is absent"""

	with step("Arrange: A request with no token field."):
		request = _refresh_request({})

	with step("Act: Call refresh."):
		response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: 400 with a Missing refresh_token message is returned."):
		assert response.status_code == 400
		assert response.data == {"error": "Missing refresh_token."}


def test_refresh_organization_not_found():
	"""Test refresh returns 404 when the org slug does not resolve"""

	with step("Arrange: A request against a slug with no matching org."):
		request = _refresh_request({"token": "old-refresh"}, org_slug="does-not-exist")

	with step("Act: Call refresh."):
		response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: 404 ORGANIZATION_NOT_FOUND is returned."):
		assert response.status_code == 404
		assert response.data == {"error": "ORGANIZATION_NOT_FOUND"}


def test_refresh_invalid_auth_driver():
	"""Test refresh returns 400 when the org's configured auth_driver isn't registered"""

	with step("Arrange: An org configured with an unknown auth_driver."):
		_make_org({"auth_driver": "not-a-real-driver"})
		request = _refresh_request({"token": "old-refresh"})

	with step("Act: Call refresh."):
		response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: 400 NOT_VALID_AUTH_DRIVER is returned."):
		assert response.status_code == 400
		assert response.data == {"error": ["NOT_VALID_AUTH_DRIVER"]}


def test_refresh_driver_error():
	"""Test refresh surfaces the driver's AuthDriverError response_data and status_code"""

	with step("Arrange: An open_id org whose refresh() call fails."):
		_make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _refresh_request({"token": "expired-refresh"})

	with step("Act: Call refresh with the driver mocked to raise."):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.refresh",
			side_effect=AuthDriverError(
				"invalid_token",
				response_data={"error": "invalid_token"},
				status_code=401,
			),
		):
			response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: The driver's response_data and status_code are surfaced."):
		assert response.status_code == 401
		assert response.data == {"error": "invalid_token"}


def test_refresh_driver_error_without_response_data():
	"""Test refresh falls back to a generic error body and 502 when the driver error carries neither"""

	with step("Arrange: An open_id org whose refresh() call fails with a bare error."):
		_make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _refresh_request({"token": "expired-refresh"})

	with step(
		"Act: Call refresh with the driver mocked to raise a bare AuthDriverError."
	):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.refresh",
			side_effect=AuthDriverError("boom"),
		):
			response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: A generic error body and 502 status are returned."):
		assert response.status_code == 502
		assert response.data == {"error": "boom"}


def test_refresh_success():
	"""Test a successful refresh returns the session dict with the resolved role attached"""

	with step("Arrange: An open_id org and a mocked successful refresh."):
		org = _make_org(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = _refresh_request({"token": "old-refresh"}, org_slug=org.slug)

	with step("Act: Call refresh with the driver mocked to succeed."):
		with patch(
			"drf_api.resources.auth.driver.open_id.Instance.refresh",
			return_value={
				"access_token": "new-tok",
				"org": org.slug,
				"refresh_token": "new-refresh",
				"user": {"password": "", "username": "bob"},
			},
		):
			response = VSAuth.as_view({"post": "refresh"})(request)

	with step("Assert: The session dict is returned with a resolved role."):
		assert response.status_code == 200
		assert response.data["access_token"] == "new-tok"
		assert response.data["role"] == "standard"
