"""This module contains tests for the SapOAuthClient helper"""

# General imports
import base64
import json
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
import requests
from allure import step

# App imports
from drf_api.resources.auth.helpers.sap_oauth_client import (
	SapOAuthClient,
	SapOAuthError,
)


def _make_client(**overrides):
	"""Build a SapOAuthClient with a fake integration config"""
	integration = {
		"base_url": "https://sap.example.com",
		"client_id": "id",
		"client_secret": "secret",
	}
	integration.update(overrides)
	return SapOAuthClient(integration)


def _make_jwt(payload):
	"""Build a dot-separated fake JWT with the given payload, no signature verification needed"""
	header_b64 = base64.urlsafe_b64encode(b"{}").decode().rstrip("=")
	payload_b64 = (
		base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
	)
	return f"{header_b64}.{payload_b64}.signature"


# ---------------------------------------------------------------------------
# __init__ / token endpoint resolution
# ---------------------------------------------------------------------------


def test_init_derives_token_endpoint_from_base_url():
	"""Test __init__ builds the token endpoint from base_url when token_endpoint isn't given"""

	with step("Arrange/Act: Build a client with only base_url."):
		client = _make_client(base_url="https://sap.example.com/")

	with step("Assert: The token endpoint is derived from base_url."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post"
		) as mock_post:
			mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
			client.exchange_code(code="abc", redirect_uri="https://app.example.com")
			assert mock_post.call_args.args[0] == "https://sap.example.com/oauth/token"


def test_init_honours_explicit_token_endpoint():
	"""Test __init__ uses an explicit token_endpoint over the derived one"""

	with step("Arrange/Act: Build a client with an explicit token_endpoint."):
		client = _make_client(token_endpoint="https://sap.example.com/custom/token")

	with step("Assert: The explicit token endpoint is used."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post"
		) as mock_post:
			mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
			client.exchange_code(code="abc", redirect_uri="https://app.example.com")
			assert mock_post.call_args.args[0] == "https://sap.example.com/custom/token"


# ---------------------------------------------------------------------------
# decode_jwt_payload
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "a well-formed JWT decodes its payload",
			"expected": {"sub": "bob"},
			"token": _make_jwt({"sub": "bob"}),
		},
		{
			"description": "a token with fewer than two parts returns an empty dict",
			"expected": {},
			"token": "not-a-jwt",
		},
		{
			"description": "an unparseable payload segment returns an empty dict",
			"expected": {},
			"token": "header.###.signature",
		},
	],
)
def test_decode_jwt_payload(payload):
	"""Test decode_jwt_payload decodes valid JWT payloads and swallows malformed ones"""

	with step(f"Arrange: {payload['description']}."):
		token = payload["token"]

	with step("Act: Call decode_jwt_payload."):
		result = SapOAuthClient.decode_jwt_payload(token)

	with step("Assert: Result matches expected."):
		assert result == payload["expected"]


# ---------------------------------------------------------------------------
# extract_user_info
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "a fully populated payload maps every field",
			"expected": {
				"email": "bob@example.com",
				"first_name": "Bob",
				"last_name": "Smith",
				"name": "Bob Smith",
				"username": "bob",
			},
			"jwt_payload": {
				"email": "bob@example.com",
				"family_name": "Smith",
				"given_name": "Bob",
				"name": "Bob Smith",
				"user_name": "bob",
			},
		},
		{
			"description": "user_name absent falls back to sub",
			"expected": {
				"email": "",
				"first_name": "",
				"last_name": "",
				"name": "",
				"username": "bob-sub",
			},
			"jwt_payload": {"sub": "bob-sub"},
		},
		{
			"description": "an empty payload maps to all-blank fields",
			"expected": {
				"email": "",
				"first_name": "",
				"last_name": "",
				"name": "",
				"username": "",
			},
			"jwt_payload": {},
		},
	],
)
def test_extract_user_info(payload):
	"""Test extract_user_info normalises a decoded JWT payload into a user-info dict"""

	with step(f"Arrange: {payload['description']}."):
		jwt_payload = payload["jwt_payload"]

	with step("Act: Call extract_user_info."):
		result = SapOAuthClient.extract_user_info(jwt_payload)

	with step("Assert: Result matches expected."):
		assert result == payload["expected"]


# ---------------------------------------------------------------------------
# exchange_code / refresh_token / __post_token
# ---------------------------------------------------------------------------


def test_exchange_code_posts_authorization_code_grant():
	"""Test exchange_code POSTs an authorization_code grant and returns the parsed response"""

	with step("Arrange: A client and a mocked successful token response."):
		client = _make_client()
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"access_token": "tok"}

	with step("Act: Call exchange_code."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post",
			return_value=mock_response,
		) as mock_post:
			result = client.exchange_code(
				code="abc", redirect_uri="https://app.example.com"
			)

	with step("Assert: The correct grant type was posted and the response returned."):
		assert mock_post.call_args.kwargs["data"]["grant_type"] == "authorization_code"
		assert mock_post.call_args.kwargs["data"]["code"] == "abc"
		assert result == {"access_token": "tok"}


def test_refresh_token_posts_refresh_token_grant():
	"""Test refresh_token POSTs a refresh_token grant and returns the parsed response"""

	with step("Arrange: A client and a mocked successful token response."):
		client = _make_client()
		mock_response = MagicMock(status_code=200)
		mock_response.json.return_value = {"access_token": "new-tok"}

	with step("Act: Call refresh_token."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post",
			return_value=mock_response,
		) as mock_post:
			result = client.refresh_token("old-refresh-token")

	with step("Assert: The correct grant type was posted and the response returned."):
		assert mock_post.call_args.kwargs["data"]["grant_type"] == "refresh_token"
		assert (
			mock_post.call_args.kwargs["data"]["refresh_token"] == "old-refresh-token"
		)
		assert result == {"access_token": "new-tok"}


def test_post_token_raises_on_request_exception():
	"""Test __post_token raises SapOAuthError with a 502 when the HTTP call itself fails"""

	with step("Arrange: A client whose POST raises a network error."):
		client = _make_client()

	with step("Act/Assert: exchange_code raises SapOAuthError."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post",
			side_effect=requests.ConnectionError("boom"),
		):
			with pytest.raises(SapOAuthError) as exc_info:
				client.exchange_code(code="abc", redirect_uri="https://app.example.com")

	with step("Assert: The error carries a 502 status code."):
		assert exc_info.value.status_code == 502


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "error_description takes priority",
			"expected_message": "bad code",
			"response_json": {
				"error": "invalid_grant",
				"error_description": "bad code",
			},
		},
		{
			"description": "falls back to the bare error field",
			"expected_message": "invalid_grant",
			"response_json": {"error": "invalid_grant"},
		},
		{
			"description": "falls back to a generic message when the body has neither",
			"expected_message": "auth_failed",
			"response_json": {},
		},
	],
)
def test_post_token_raises_on_non_200_with_json_body(payload):
	"""Test __post_token raises SapOAuthError using the most specific message available in the JSON body"""

	with step(f"Arrange: {payload['description']}."):
		client = _make_client()
		mock_response = MagicMock(status_code=400)
		mock_response.json.return_value = payload["response_json"]

	with step("Act/Assert: exchange_code raises SapOAuthError."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post",
			return_value=mock_response,
		):
			with pytest.raises(SapOAuthError) as exc_info:
				client.exchange_code(code="abc", redirect_uri="https://app.example.com")

	with step("Assert: The most specific available message was used."):
		assert str(exc_info.value) == payload["expected_message"]
		assert exc_info.value.status_code == 400


def test_post_token_raises_on_non_200_with_unparseable_body():
	"""Test __post_token falls back to an empty response_data when the error body isn't valid JSON"""

	with step("Arrange: A non-200 response whose .json() raises."):
		client = _make_client()
		mock_response = MagicMock(status_code=500)
		mock_response.json.side_effect = ValueError("not json")

	with step("Act/Assert: exchange_code raises SapOAuthError."):
		with patch(
			"drf_api.resources.auth.helpers.sap_oauth_client.requests.post",
			return_value=mock_response,
		):
			with pytest.raises(SapOAuthError) as exc_info:
				client.exchange_code(code="abc", redirect_uri="https://app.example.com")

	with step("Assert: The generic fallback message and empty response_data are used."):
		assert str(exc_info.value) == "auth_failed"
		assert exc_info.value.response_data == {}
