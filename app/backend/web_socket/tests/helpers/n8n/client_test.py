"""This module contains tests for the n8n client's B1S credential handoff at fire time"""

# General imports
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Lib imports
import httpx
import pytest
from allure import step
from asgiref.sync import async_to_sync
from django.utils import timezone

# App imports
from drf_api.models import MOrganization, MSessionProxy
from web_socket.helpers.n8n.client import (
	N8nClient,
	N8nClientError,
	N8nWebhookNotReadyError,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _make_org(integration, slug="acme"):
	"""Create a persisted MOrganization instance with the given integration config"""
	return MOrganization.objects.create(integration=integration, name=slug, slug=slug)


def _make_user(access_token="opaque-token"):
	"""Build a user stand-in exposing to_dict() like WsUser/_DictShim"""
	user = MagicMock()
	user.to_dict.return_value = {
		"access_token": access_token,
		"database": "",
		"user": {"password": "", "username": "bob"},
	}
	return user


def test_resolve_session_payload_open_id_unchanged():
	"""Test _resolve_session_payload leaves the session dict untouched for non-b1s orgs"""

	with step("Arrange: An open_id organization dict and a user exposing to_dict()."):
		client = N8nClient()
		organization_dict = {"integration": {"auth_driver": "open_id"}}
		user = _make_user()

	with step("Act: Call _resolve_session_payload."):
		result = async_to_sync(
			client._resolve_session_payload  # pylint: disable=protected-access
		)(organization_dict, user)

	with step("Assert: The session dict is returned unmodified."):
		assert result == user.to_dict.return_value


def test_resolve_session_payload_b1s_unknown_token():
	"""Test _resolve_session_payload falls back to the plain session dict when the token doesn't resolve"""

	with step(
		"Arrange: A b1s organization dict and a user carrying an unresolvable token."
	):
		client = N8nClient()
		organization_dict = {"integration": {"auth_driver": "b1s"}}
		user = _make_user(access_token="does-not-exist")

	with step("Act: Call _resolve_session_payload."):
		result = async_to_sync(
			client._resolve_session_payload  # pylint: disable=protected-access
		)(organization_dict, user)

	with step("Assert: The session dict is returned unmodified."):
		assert result == user.to_dict.return_value


def test_resolve_session_payload_b1s_swaps_decrypted_credentials():
	"""Test _resolve_session_payload swaps in the real decrypted username/password for a b1s org"""

	with step("Arrange: A live MSessionProxy and a user carrying its opaque token."):
		client = N8nClient()
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "real-secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="opaque-token",
			username="bob",
		)
		organization_dict = {"integration": {"auth_driver": "b1s"}}
		user = _make_user()

	with step("Act: Call _resolve_session_payload."):
		result = async_to_sync(
			client._resolve_session_payload  # pylint: disable=protected-access
		)(organization_dict, user)

	with step("Assert: The real credentials and connection_key were substituted in."):
		assert result["database"] == "TESTDB"
		assert result["user"] == {"password": "real-secret", "username": "bob"}


def test_fire_sends_decrypted_b1s_credentials_to_n8n():
	"""Test fire posts the decrypted B1S credentials in the outgoing payload, not the opaque token"""

	with step(
		"Arrange: A live MSessionProxy, a mocked httpx client, and a mocked state store."
	):
		client = N8nClient()
		org = _make_org(
			{"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"}
		)
		MSessionProxy.objects.create(
			auth_driver="b1s",
			connection_key="TESTDB",
			credentials={"password": "real-secret", "username": "bob"},
			expires_at=timezone.now() + timedelta(hours=1),
			org=org,
			token="opaque-token",
			username="bob",
		)
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "b1s"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call fire."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(client.fire)(
				message="hi",
				group_name="grp",
				session_id=1,
				organization=organization,
				state=state,
				user=user,
			)

	with step("Assert: The outgoing payload carries the decrypted credentials."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["session"]["database"] == "TESTDB"
		assert sent_payload["session"]["user"] == {
			"password": "real-secret",
			"username": "bob",
		}


def test_fire_includes_process_definition_and_last_bot_message_when_present():
	"""Test fire includes process_definition/last_bot_message in the payload only when set"""

	with step(
		"Arrange: A state carrying both optional fields, and a mocked httpx client."
	):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(
			load=AsyncMock(
				return_value={
					"last_bot_message": "What is the amount?",
					"process_definition": {"name": "Create PO"},
				}
			)
		)

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call fire."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(client.fire)(
				message="hi",
				group_name="grp",
				session_id=1,
				organization=organization,
				state=state,
				user=user,
			)

	with step("Assert: Both optional fields were included in the outgoing payload."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["process_definition"] == {"name": "Create PO"}
		assert sent_payload["last_bot_message"] == "What is the amount?"


def test_fire_raises_n8n_client_error_on_request_error():
	"""Test fire wraps a raw httpx.RequestError as an N8nClientError"""

	with step("Arrange: A mocked httpx client whose post() raises a RequestError."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(
			side_effect=httpx.RequestError("connection failed")
		)
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act/Assert: fire raises N8nClientError."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			with pytest.raises(N8nClientError, match="connection failed"):
				async_to_sync(client.fire)(
					message="hi",
					group_name="grp",
					session_id=1,
					organization=organization,
					state=state,
					user=user,
				)


def test_fire_raises_webhook_not_ready_on_404():
	"""Test fire raises N8nWebhookNotReadyError when the webhook responds 404"""

	with step("Arrange: A mocked httpx client returning a 404 response."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=404))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act/Assert: fire raises N8nWebhookNotReadyError."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			with pytest.raises(N8nWebhookNotReadyError) as exc_info:
				async_to_sync(client.fire)(
					message="hi",
					group_name="grp",
					session_id=1,
					organization=organization,
					state=state,
					user=user,
				)

	with step("Assert: The error carries a 404 status code."):
		assert exc_info.value.status_code == 404


def test_fire_raises_n8n_client_error_on_other_4xx_5xx():
	"""Test fire raises N8nClientError for any non-404 error response"""

	with step("Arrange: A mocked httpx client returning a 500 response."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=500))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act/Assert: fire raises N8nClientError."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			with pytest.raises(N8nClientError) as exc_info:
				async_to_sync(client.fire)(
					message="hi",
					group_name="grp",
					session_id=1,
					organization=organization,
					state=state,
					user=user,
				)

	with step("Assert: The error carries the response's status code."):
		assert exc_info.value.status_code == 500
