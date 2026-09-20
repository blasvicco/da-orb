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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
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


def test_fire_includes_last_bot_message_when_present():
	"""Test fire includes last_bot_message in the payload only when set"""

	with step("Arrange: A state carrying last_bot_message, and a mocked httpx client."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(
			load=AsyncMock(return_value={"last_bot_message": "What is the amount?"})
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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: last_bot_message was included in the outgoing payload."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["last_bot_message"] == "What is the amount?"


def test_fire_includes_intention_graph_fields_in_the_payload():
	"""Test fire includes intention_nodes/active_node_id in the payload"""

	with step(
		"Arrange: A state carrying intention-graph fields, and a mocked httpx client."
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
					"active_node_id": "n1",
					"intention_nodes": {"n1": {"id": "n1", "status": "active"}},
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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step(
		"Assert: Both intention-graph fields were included in the outgoing payload."
	):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["active_node_id"] == "n1"
		assert sent_payload["intention_nodes"] == {
			"n1": {"id": "n1", "status": "active"}
		}


def test_fire_defaults_intention_graph_fields_when_state_has_none():
	"""Test fire defaults intention_nodes to {} and active_node_id to None"""

	with step(
		"Arrange: A state with no intention-graph fields, and a mocked httpx client."
	):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: The intention-graph fields default to empty/None."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["active_node_id"] is None
		assert sent_payload["intention_nodes"] == {}


def test_fire_includes_bucket_file_ids_when_set():
	"""Test fire sends the bucket_file_ids references as-is when the caller passes them"""

	with step("Arrange: A mocked httpx client and state."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call fire with bucket_file_ids."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(client.fire)(
				bucket_file_ids=[42, 7],
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: The references were included in the outgoing payload verbatim."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["bucket_file_ids"] == [42, 7]


def test_fire_defaults_bucket_file_ids_to_empty_list():
	"""Test fire sends [] for bucket_file_ids when the caller doesn't pass any"""

	with step("Arrange: A mocked httpx client and state."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call fire without bucket_file_ids."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(client.fire)(
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: bucket_file_ids defaults to an empty list."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["bucket_file_ids"] == []


def test_fire_includes_language_verbatim_in_the_payload():
	"""Test fire sends the caller's language as-is at the top level of the payload, with no default of its own"""

	with step("Arrange: A mocked httpx client and state."):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={}))

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call fire with language='en'."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(client.fire)(
				expertise_level=2,
				group_name="grp",
				language="en",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step(
		"Assert: The payload's top-level language matches the caller's, unchanged."
	):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["language"] == "en"


def test_fire_payload_has_no_unexpected_keys():
	"""Test fire's payload only ever contains the fixed set of keys the workflow actually reads"""

	with step(
		"Arrange: A mocked httpx client and a state carrying last_bot_message (the one conditional key)."
	):
		client = N8nClient()
		organization = MagicMock()
		organization.safe_to_dict = MagicMock(
			return_value={"integration": {"auth_driver": "open_id"}}
		)
		user = _make_user()
		state = MagicMock(load=AsyncMock(return_value={"last_bot_message": "hi"}))

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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=organization,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: The payload contains exactly the fixed, known key set."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert set(sent_payload.keys()) == {
			"active_node_id",
			"bucket_file_ids",
			"expertise_level",
			"group_name",
			"intention_nodes",
			"language",
			"last_bot_message",
			"message",
			"organization",
			"session",
			"session_id",
		}


def test_fire_trims_organization_and_session_to_only_fields_any_workflow_reads():
	"""Test fire strips organization/session down to the handful of fields any v14 workflow node
	actually reads (organization.integration/slug, session.access_token/database/user) -- the
	rest (name/plan/seat_limit/created_on/id, expires_at/id_token/org/refresh_token) would
	otherwise round-trip forever through every intention_nodes[id] copy stored in n8n_state."""

	with step(
		"Arrange: A real org (name/plan/seat_limit set via defaults) and a session carrying "
		"oauth-only fields no workflow node reads."
	):
		client = N8nClient()
		org = _make_org({"auth_driver": "b1s", "base_url": "https://fake.example.com/b1s/v1"})
		user = MagicMock()
		user.to_dict.return_value = {
			"access_token": "opaque-token",
			"database": "",
			"expires_at": 123,
			"id_token": "eyFakeJwt",
			"org": "acme",
			"refresh_token": "refresh-secret",
			"user": {"password": "", "username": "bob"},
		}
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
				expertise_level=2,
				group_name="grp",
				language="es",
				message="hi",
				organization=org,
				session_id=1,
				state=state,
				user=user,
			)

	with step("Assert: organization/session are trimmed to exactly the referenced fields."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert set(sent_payload["organization"].keys()) == {"integration", "slug"}
		assert sent_payload["organization"]["slug"] == "acme"
		assert set(sent_payload["session"].keys()) == {"access_token", "database", "user"}
		assert sent_payload["session"]["access_token"] == "opaque-token"


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
					expertise_level=2,
					group_name="grp",
					language="es",
					message="hi",
					organization=organization,
					session_id=1,
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
					expertise_level=2,
					group_name="grp",
					language="es",
					message="hi",
					organization=organization,
					session_id=1,
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
					expertise_level=2,
					group_name="grp",
					language="es",
					message="hi",
					organization=organization,
					session_id=1,
					state=state,
					user=user,
				)

	with step("Assert: The error carries the response's status code."):
		assert exc_info.value.status_code == 500
