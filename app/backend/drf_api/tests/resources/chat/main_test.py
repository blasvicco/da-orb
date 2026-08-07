"""This module contains tests for the chat resource connection_key scoping"""

# General imports
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode
from uuid import uuid4

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync
from django.utils import timezone
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MChatMessage, MChatSession, MOrganization, MSeat, MUsageEvent
from drf_api.resources.chat.main import VSChat, _release_and_refire
from drf_api.resources.chat.permission import PN8nCallback
from web_socket.helpers.n8n.queue import N8nQueueState

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an active seat for the test user"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	MSeat.objects.create(org=org, status="active", username="bob")
	return org


def _make_request(method, org, connection_key="", query=None, username=""):
	"""Build a DRF-compatible request with org/auth headers already attached"""
	path = f"/?{urlencode(query)}" if query else "/"
	build = getattr(_factory, method)
	request = build(
		path,
		HTTP_AUTHORIZATION="Bearer sometoken",
		HTTP_X_SAP_CONNECTION_KEY=connection_key,
		HTTP_X_SAP_USERNAME=username,
	)
	request.get_org_slug = lambda: org.slug
	return request


def test_sessions_scoped_by_connection_key():
	"""Test sessions only returns rows matching the requesting connection_key"""

	with step("Arrange: Two sessions for the same org/username, different databases."):
		org = _make_org()
		matching = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		MChatSession.objects.create(connection_key="OTHERDB", org=org, username="bob")
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: Only the matching-connection_key session is returned."):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [matching.id]


def test_sessions_includes_n8n_state_for_reloaded_intention_graph():
	"""Test sessions returns n8n_state so a reloaded session can rebuild its intention graph"""

	with step("Arrange: A session with a persisted n8n_state snapshot."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			n8n_state={"intention_nodes": [{"id": "p1#0", "status": "completed"}]},
			org=org,
			username="bob",
		)
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: The session's n8n_state is included in the response."):
		assert response.status_code == 200
		row = next(entry for entry in response.data if entry["id"] == session.id)
		assert row["n8n_state"] == {
			"intention_nodes": [{"id": "p1#0", "status": "completed"}]
		}


def test_sessions_returns_tokens_used_sum():
	"""Test sessions annotates tokens_used with the sum of the session's token_usage events"""

	with step(
		"Arrange: A session with two token_usage events and one process_execution event."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		now = timezone.now()
		MUsageEvent.objects.create(
			connection_key="TESTDB",
			event_type="token_usage",
			occurred_on=now,
			org=org,
			session=session,
			total_tokens=15,
			username="bob",
		)
		MUsageEvent.objects.create(
			connection_key="TESTDB",
			event_type="token_usage",
			occurred_on=now,
			org=org,
			session=session,
			total_tokens=25,
			username="bob",
		)
		MUsageEvent.objects.create(
			connection_key="TESTDB",
			event_type="process_execution",
			occurred_on=now,
			org=org,
			session=session,
			username="bob",
		)
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: tokens_used sums only the token_usage events' total_tokens."):
		assert response.status_code == 200
		assert response.data[0]["tokens_used"] == 40


def test_sessions_returns_empty_list_when_identity_resolves_differently_mid_request(
	mocker,
):
	"""Test sessions defensively returns an empty list if identity resolution changes mid-request"""

	with step(
		"Arrange: A valid seat for the permission check, then a blank identity for the view body."
	):
		org = _make_org()
		request = _make_request("get", org, connection_key="TESTDB", username="bob")
		mocker.patch.object(
			VSChat,
			"_get_org_and_user",
			side_effect=[(org, "bob", "TESTDB"), (None, "", "")],
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: An empty list is returned without error."):
		assert response.status_code == 200
		assert response.data == []


def test_sessions_returns_zero_tokens_when_no_usage_events():
	"""Test sessions annotates tokens_used as 0 when the session has no usage events"""

	with step("Arrange: A session with no MUsageEvent rows."):
		org = _make_org()
		MChatSession.objects.create(connection_key="TESTDB", org=org, username="bob")
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: tokens_used is 0."):
		assert response.status_code == 200
		assert response.data[0]["tokens_used"] == 0


def test_messages_404_on_mismatched_connection_key():
	"""Test messages 404s when the requesting connection_key does not match the session"""

	with step("Arrange: A session scoped to TESTDB, request scoped to OTHERDB."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_request(
			"get",
			org,
			connection_key="OTHERDB",
			query={"session_id": session.id},
			username="bob",
		)

	with step("Act: Call messages."):
		response = VSChat.as_view({"get": "messages"})(request)

	with step("Assert: A 404 is returned."):
		assert response.status_code == 404


def test_messages_returns_matching_session():
	"""Test messages returns the message list when the connection_key matches"""

	with step("Arrange: A session and message scoped to TESTDB."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		MChatMessage.objects.create(
			session=session, text="hello", timestamp=timezone.now(), type="user"
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"session_id": session.id},
			username="bob",
		)

	with step("Act: Call messages."):
		response = VSChat.as_view({"get": "messages"})(request)

	with step("Assert: The message is returned."):
		assert response.status_code == 200
		assert len(response.data) == 1
		assert response.data[0]["text"] == "hello"


def test_delete_session_404_on_mismatched_connection_key():
	"""Test delete_session 404s when the requesting connection_key does not match the session"""

	with step("Arrange: A session scoped to TESTDB, request scoped to OTHERDB."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_request(
			"delete",
			org,
			connection_key="OTHERDB",
			query={"session_id": session.id},
			username="bob",
		)

	with step("Act: Call delete_session."):
		response = VSChat.as_view({"delete": "delete_session"})(request)

	with step("Assert: A 404 is returned."):
		assert response.status_code == 404


def test_delete_session_removes_matching_session():
	"""Test delete_session deletes the session when org, username, and connection_key all match"""

	with step("Arrange: A session scoped to TESTDB/bob."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_request(
			"delete",
			org,
			connection_key="TESTDB",
			query={"session_id": session.id},
			username="bob",
		)

	with step("Act: Call delete_session."):
		response = VSChat.as_view({"delete": "delete_session"})(request)

	with step("Assert: The session was deleted."):
		assert response.status_code == 204
		assert not MChatSession.objects.filter(id=session.id).exists()


def _make_callback_request(data, org, secret="test-secret"):
	"""Build a DRF-compatible n8n_callback POST request with a valid shared-secret header"""
	request = _factory.post("/", data, format="json", HTTP_X_N8N_SECRET=secret)
	request.get_org_slug = lambda: org.slug
	return request


def test_n8n_callback_records_token_usage_event(settings):
	"""Test n8n_callback persists a token_usage MUsageEvent when extra.usage is present"""

	with step("Arrange: A session and a callback payload carrying token usage."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_callback_request(
			{
				"extra": {
					"usage": {
						"completion_tokens": 5,
						"model": "gpt-5-nano",
						"prompt_tokens": 10,
						"total_tokens": 15,
					}
				},
				"group_name": "chat_1_bob_abc",
				"session_id": session.id,
				"text": "hi",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step(
		"Assert: A token_usage event was recorded with the right identity and totals."
	):
		assert response.status_code == 200
		event = MUsageEvent.objects.get(event_type="token_usage", org=org)
		assert event.connection_key == "TESTDB"
		assert event.model_name == "gpt-5-nano"
		assert event.prompt_tokens == 10
		assert event.completion_tokens == 5
		assert event.total_tokens == 15
		assert event.username == "bob"


def test_n8n_callback_records_process_execution_event(settings):
	"""Test n8n_callback persists a process_execution MUsageEvent when processes is present"""

	with step(
		"Arrange: A session and a callback payload carrying a disambiguation list."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_abc",
				"processes": [{"name": "create_purchase_order"}],
				"session_id": session.id,
				"text": "Which process?",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step("Assert: A process_execution event was recorded."):
		assert response.status_code == 200
		event = MUsageEvent.objects.get(event_type="process_execution", org=org)
		assert event.process_name == "create_purchase_order"
		assert event.username == "bob"


def test_n8n_callback_records_process_execution_event_prefers_definition_name(settings):
	"""Test n8n_callback uses process_definition.name over the raw numeric process_id"""

	with step(
		"Arrange: A session and a callback payload carrying state with a numeric "
		"process_id but no disambiguation list."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_def",
				"session_id": session.id,
				"state": {
					"process_definition": {"name": "Create Purchase Request"},
					"process_id": 1,
				},
				"text": "Please provide the required fields.",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step(
		"Assert: The process_execution event uses the definition's display name."
	):
		assert response.status_code == 200
		event = MUsageEvent.objects.get(event_type="process_execution", org=org)
		assert event.process_name == "Create Purchase Request"


def test_n8n_callback_records_no_usage_event_when_nothing_to_report(settings):
	"""Test n8n_callback creates no MUsageEvent when the payload carries neither usage nor processes"""

	with step("Arrange: A session and a plain text-only callback payload."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_abc",
				"session_id": session.id,
				"text": "hi",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step("Assert: No usage event was recorded."):
		assert response.status_code == 200
		assert not MUsageEvent.objects.filter(org=org).exists()


def test_n8n_callback_reset_process_clears_stale_state(settings):
	"""Test n8n_callback honours reset_process=True, clearing a field instead of keeping the stale value"""

	with step("Arrange: A session with a process_id already persisted in Redis state."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		group_name = f"chat_reset_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"process_definition": {"name": "Create PO"},
					"process_id": 5,
				},
				"text": "step 1",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step(
		"Act: Send a second callback with reset_process=True and a null process_id."
	):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"process_id": None, "reset_process": True},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step("Assert: The stale process_id was cleared instead of preserved."):
		session.refresh_from_db()
		assert session.n8n_state["process_id"] is None


def test_n8n_callback_reset_process_clears_active_node_id(settings):
	"""Test n8n_callback honours reset_process=True for active_node_id, mirroring process_id"""

	with step(
		"Arrange: A session with an active_node_id already persisted in Redis state."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		group_name = f"chat_reset_node_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"active_node_id": "n1",
					"intention_nodes": [{"id": "n1", "status": "active"}],
					"process_id": 5,
				},
				"text": "step 1",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step(
		"Act: Send a second callback with reset_process=True and a null active_node_id."
	):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"active_node_id": None,
					"process_id": None,
					"reset_process": True,
				},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step("Assert: The stale active_node_id was cleared instead of preserved."):
		session.refresh_from_db()
		assert session.n8n_state["active_node_id"] is None


def test_n8n_callback_persists_parent_override_id_until_reset(settings):
	"""Test n8n_callback persists parent_override_id across turns and clears it only via reset_process"""

	with step("Arrange: A session with a first callback carrying parent_override_id."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		group_name = f"chat_override_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"parent_override_id": "n0#0"},
				"text": "step 1",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step(
		"Act: Send a second callback that omits parent_override_id entirely (e.g. a clarifying follow-up)."
	):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"process_id": 9},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step("Assert: parent_override_id survives untouched."):
		session.refresh_from_db()
		assert session.n8n_state["parent_override_id"] == "n0#0"

	with step(
		"Act: Send a third callback with reset_process=True consuming the override."
	):
		third_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"parent_override_id": None, "reset_process": True},
				"text": "step 3",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			third_request
		)

	with step("Assert: parent_override_id was cleared once consumed."):
		session.refresh_from_db()
		assert session.n8n_state["parent_override_id"] is None


def test_n8n_callback_persists_batch_confirmation_fields_until_explicitly_cleared(
	settings,
):
	"""Test n8n_callback persists awaiting_batch_confirmation/pending_batch_items across
	a turn that omits them, clearing them only once a later turn explicitly does so"""

	with step(
		"Arrange: A session with a first callback carrying pending batch-confirmation fields."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		group_name = f"chat_batch_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"awaiting_batch_confirmation": True,
					"pending_batch_items": [
						{"process_name": "Create Purchase Request"}
					],
				},
				"text": "Encontré 3 solicitudes de compra. ¿Confirmas?",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step(
		"Act: Send a second callback that omits both batch-confirmation fields entirely."
	):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"process_id": 9},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step("Assert: Both fields survive untouched."):
		session.refresh_from_db()
		assert session.n8n_state["awaiting_batch_confirmation"] is True
		assert session.n8n_state["pending_batch_items"] == [
			{"process_name": "Create Purchase Request"}
		]

	with step(
		"Act: Send a third callback that explicitly clears both fields (user confirmed)."
	):
		third_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"awaiting_batch_confirmation": False,
					"pending_batch_items": [],
				},
				"text": "step 3",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			third_request
		)

	with step("Assert: Both fields were cleared once consumed."):
		session.refresh_from_db()
		assert session.n8n_state["awaiting_batch_confirmation"] is False
		assert session.n8n_state["pending_batch_items"] == []


def test_n8n_callback_persists_intention_nodes_and_paused_node_ids(settings):
	"""Test n8n_callback persists intention_nodes/paused_node_ids and falls back to the current value when omitted"""

	with step(
		"Arrange: A session and a first callback carrying intention-graph fields."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB", org=org, username="bob"
		)
		group_name = f"chat_nodes_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"intention_nodes": [{"id": "n1", "status": "paused"}],
					"paused_node_ids": ["n1"],
				},
				"text": "step 1",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step("Act: Send a second callback that omits both fields entirely."):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"process_id": 9},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step(
		"Assert: The previously persisted intention-graph fields survive untouched."
	):
		session.refresh_from_db()
		assert session.n8n_state["intention_nodes"] == [
			{"id": "n1", "status": "paused"}
		]
		assert session.n8n_state["paused_node_ids"] == ["n1"]


def test_n8n_callback_ignores_missing_session(settings):
	"""Test n8n_callback silently skips persistence when session_id doesn't match any session"""

	with step("Arrange: A callback payload referencing a non-existent session."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		request = _make_callback_request(
			{
				"group_name": "chat_missing_session",
				"session_id": 9999999,
				"text": "hi",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step("Assert: 200 is still returned and no message was persisted."):
		assert response.status_code == 200
		assert not MChatMessage.objects.filter(text="hi").exists()


# ---------------------------------------------------------------------------
# _release_and_refire
# ---------------------------------------------------------------------------


def _set_pending(group_name, pending):
	"""Write a pending payload via a fresh N8nQueueState (each async_to_sync call needs its own client)"""
	queue = N8nQueueState(group_name=group_name)
	try:
		async_to_sync(queue.set_pending)(pending)
	finally:
		async_to_sync(queue.close)()


def _pop_pending(group_name):
	"""Pop the pending payload via a fresh N8nQueueState (each async_to_sync call needs its own client)"""
	queue = N8nQueueState(group_name=group_name)
	try:
		return async_to_sync(queue.pop_pending)()
	finally:
		async_to_sync(queue.close)()


def test_release_and_refire_fires_the_pending_message():
	"""Test _release_and_refire pops and fires a message queued behind the released lock"""

	with step("Arrange: A pending message queued for this chat group."):
		group_name = f"chat_test_{uuid4()}"
		pending = {
			"expertise_level": 2,
			"group_name": group_name,
			"message": "queued message",
			"organization": {
				"integration": {
					"auth_driver": "open_id",
					"base_url": "https://sap.example.com",
				}
			},
			"session_id": None,
			"user": {"password": "", "username": "bob"},
		}
		_set_pending(group_name, pending)

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call _release_and_refire."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(_release_and_refire)(group_name)

	with step(
		"Assert: The queued message was fired and cleared from the pending slot."
	):
		mock_http_client.post.assert_called_once()
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["message"] == "queued message"
		assert _pop_pending(group_name) is None


def test_release_and_refire_forwards_active_node_override():
	"""Test _release_and_refire forwards a queued message's active_node_override to n8n"""

	with step(
		"Arrange: A pending message queued with a one-shot active_node_override."
	):
		group_name = f"chat_test_{uuid4()}"
		pending = {
			"active_node_override": "n2#0",
			"expertise_level": 2,
			"group_name": group_name,
			"message": "queued message",
			"organization": {
				"integration": {
					"auth_driver": "open_id",
					"base_url": "https://sap.example.com",
				}
			},
			"session_id": None,
			"user": {"password": "", "username": "bob"},
		}
		_set_pending(group_name, pending)

		mock_http_client = AsyncMock()
		mock_http_client.post = AsyncMock(return_value=MagicMock(status_code=200))
		mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
		mock_http_client.__aexit__ = AsyncMock(return_value=False)

	with step("Act: Call _release_and_refire."):
		with patch(
			"web_socket.helpers.n8n.client.httpx.AsyncClient",
			return_value=mock_http_client,
		):
			async_to_sync(_release_and_refire)(group_name)

	with step("Assert: The outgoing payload carries the queued active_node_override."):
		sent_payload = mock_http_client.post.call_args.kwargs["json"]
		assert sent_payload["active_node_override"] == "n2#0"


def test_release_and_refire_requeues_when_another_execution_started(mocker):
	"""Test _release_and_refire puts the message back if another execution grabbed the lock first"""

	with step(
		"Arrange: A pending message and try_start() mocked to report the lock as taken."
	):
		group_name = f"chat_test_{uuid4()}"
		pending = {"group_name": group_name, "message": "queued message"}
		_set_pending(group_name, pending)
		mocker.patch.object(N8nQueueState, "try_start", AsyncMock(return_value=False))

	with step("Act: Call _release_and_refire."):
		async_to_sync(_release_and_refire)(group_name)

	with step("Assert: The message was put back into the pending slot."):
		assert _pop_pending(group_name) == pending


def test_release_and_refire_releases_lock_on_fire_failure(mocker):
	"""Test _release_and_refire releases the lock again if firing the queued message fails"""

	with step("Arrange: A pending message and a client.fire that raises."):
		group_name = f"chat_test_{uuid4()}"
		pending = {"group_name": group_name, "message": "queued message"}
		_set_pending(group_name, pending)
		mocker.patch(
			"web_socket.helpers.n8n.client.N8nClient.fire",
			new=AsyncMock(side_effect=RuntimeError("boom")),
		)
		release_mock = mocker.patch.object(N8nQueueState, "release", AsyncMock())

	with step("Act: Call _release_and_refire."):
		async_to_sync(_release_and_refire)(group_name)

	with step("Assert: The lock was released both at entry and after the failure."):
		assert release_mock.call_count == 2
