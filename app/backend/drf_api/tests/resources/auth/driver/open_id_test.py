"""This module contains tests for the Open ID authentication driver"""

# General imports
import base64
import json
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.auth.driver.abstract import AuthDriverError
from drf_api.resources.auth.driver.open_id import Instance
from drf_api.resources.auth.helpers import SapOAuthError


def _make_driver():
	"""Build an Open ID driver instance with a fake integration config"""
	return Instance(
		{
			"auth_driver": "open_id",
			"base_url": "https://sap.example.com",
			"client_id": "id",
			"client_secret": "secret",
		}
	)


def test_authenticate_exchanges_code_for_a_session():
	"""Test authenticate exchanges the code for tokens and returns a normalised session dict"""

	with step("Arrange: A driver whose client returns a successful token response."):
		driver = _make_driver()

	with step("Act: Call authenticate."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"exchange_code",
			return_value={"access_token": "tok", "expires_in": 3600},
		):
			session_data = driver.authenticate(
				code="abc", org="acme", redirect_uri="https://app.example.com"
			)

	with step("Assert: A normalised session dict is returned."):
		assert session_data["access_token"] == "tok"
		assert session_data["org"] == "acme"


def test_authenticate_wraps_sap_oauth_error():
	"""Test authenticate re-raises a SapOAuthError from the client as an AuthDriverError"""

	with step("Arrange: A driver whose client raises SapOAuthError."):
		driver = _make_driver()

	with step("Act/Assert: authenticate raises AuthDriverError."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"exchange_code",
			side_effect=SapOAuthError("invalid_grant", status_code=400),
		):
			with pytest.raises(AuthDriverError, match="invalid_grant") as exc_info:
				driver.authenticate(
					code="bad", org="acme", redirect_uri="https://app.example.com"
				)

	with step("Assert: The status code is carried through."):
		assert exc_info.value.status_code == 400


def test_refresh_exchanges_refresh_token_for_a_session():
	"""Test refresh exchanges the refresh token for a new session dict"""

	with step("Arrange: A driver whose client returns a successful refresh response."):
		driver = _make_driver()

	with step("Act: Call refresh."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"refresh_token",
			return_value={"access_token": "new-tok", "expires_in": 3600},
		):
			session_data = driver.refresh(org="acme", refresh_token="old-refresh")

	with step("Assert: A normalised session dict is returned."):
		assert session_data["access_token"] == "new-tok"
		assert session_data["org"] == "acme"


def test_refresh_falls_back_to_the_original_refresh_token_when_none_is_returned():
	"""Test refresh keeps the original refresh_token when the response doesn't carry a new one"""

	with step("Arrange: A driver whose client response has no refresh_token."):
		driver = _make_driver()

	with step("Act: Call refresh."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"refresh_token",
			return_value={"access_token": "new-tok"},
		):
			session_data = driver.refresh(org="acme", refresh_token="old-refresh")

	with step("Assert: The original refresh token is kept."):
		assert session_data["refresh_token"] == "old-refresh"


def test_refresh_wraps_sap_oauth_error():
	"""Test refresh re-raises a SapOAuthError from the client as an AuthDriverError"""

	with step("Arrange: A driver whose client raises SapOAuthError."):
		driver = _make_driver()

	with step("Act/Assert: refresh raises AuthDriverError."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"refresh_token",
			side_effect=SapOAuthError("invalid_token", status_code=401),
		):
			with pytest.raises(AuthDriverError, match="invalid_token") as exc_info:
				driver.refresh(org="acme", refresh_token="expired")

	with step("Assert: The status code is carried through."):
		assert exc_info.value.status_code == 401


def test_build_session_extracts_user_info_from_id_token():
	"""Test authenticate decodes the id_token and populates user info when one is returned"""

	with step("Arrange: A driver whose client response carries an id_token."):
		driver = _make_driver()
		payload_b64 = (
			base64.urlsafe_b64encode(json.dumps({"user_name": "bob"}).encode())
			.decode()
			.rstrip("=")
		)
		id_token = f"header.{payload_b64}.signature"

	with step("Act: Call authenticate."):
		with patch.object(
			driver._client,  # pylint: disable=protected-access
			"exchange_code",
			return_value={"access_token": "tok", "id_token": id_token},
		):
			session_data = driver.authenticate(
				code="abc", org="acme", redirect_uri="https://app.example.com"
			)

	with step("Assert: The user info decoded from the id_token is present."):
		assert session_data["id_token"] == id_token
		assert session_data["user"]["username"] == "bob"


def test_resolve_identity_uses_the_header_trust_default():
	"""Test resolve_identity keeps the base class's header-trust behaviour"""

	with step("Arrange: A driver and a request carrying SAP identity headers."):
		driver = _make_driver()
		request = MagicMock(
			headers={"X-SAP-Connection-Key": "SBODEMOUS", "X-SAP-Username": "bob"}
		)

	with step("Act: Call resolve_identity."):
		username, connection_key = driver.resolve_identity(request)

	with step("Assert: Identity is read straight from the headers."):
		assert username == "bob"
		assert connection_key == "SBODEMOUS"


def test_resolve_session_payload_passes_through_unchanged():
	"""Test resolve_session_payload keeps the base class's pass-through behaviour"""

	with step("Arrange: A driver and a session dict."):
		driver = _make_driver()
		session_dict = {"access_token": "tok"}

	with step("Act: Call resolve_session_payload."):
		result = driver.resolve_session_payload(session_dict)

	with step("Assert: The session dict is returned unchanged."):
		assert result == session_dict


def test_login_not_supported():
	"""Test login raises METHOD_NOT_ALLOWED since Open ID has no credential-based login"""

	with step("Arrange: An Open ID driver instance and a dummy request."):
		driver = Instance(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = MagicMock()

	with step("Act/Assert: login raises METHOD_NOT_ALLOWED."):
		with pytest.raises(AuthDriverError, match="METHOD_NOT_ALLOWED") as exc_info:
			driver.login(request, org="acme")

	with step("Assert: The error carries a 405 status code."):
		assert exc_info.value.status_code == 405
