"""This module contains tests for the auth viewset login/callback actions"""

# General imports
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MOrganization, MSessionProxy
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
