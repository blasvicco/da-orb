"""This module contains tests for the chat resource connection_key scoping"""

# General imports
import threading
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
from drf_api.models import (
	MChatMessage,
	MChatSession,
	MOrganization,
	MProject,
	MSeat,
	MUsageEvent,
)
from drf_api.resources.chat.main import (
	VSChat,
	_collect_and_record_usage,
	_release_and_refire,
)
from drf_api.resources.chat.permission import PN8nCallback
from web_socket.helpers.n8n.queue import N8nQueueState

_REAL_THREAD = threading.Thread  # pylint: disable=invalid-name

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
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MChatSession.objects.create(
			connection_key="OTHERDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "OTHERDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": matching.project_id},
			username="bob",
		)

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
			n8n_state={
				"intention_nodes": {"p1#0": {"id": "p1#0", "status": "completed"}}
			},
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": session.project_id},
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: The session's n8n_state is included in the response."):
		assert response.status_code == 200
		row = next(entry for entry in response.data if entry["id"] == session.id)
		assert row["n8n_state"] == {
			"intention_nodes": {"p1#0": {"id": "p1#0", "status": "completed"}}
		}


def test_sessions_returns_tokens_used_sum():
	"""Test sessions annotates tokens_used with the sum of the session's token_usage events"""

	with step(
		"Arrange: A session with two token_usage events and one process_execution event."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": session.project_id},
			username="bob",
		)

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
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": session.project_id},
			username="bob",
		)

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
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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


def test_delete_session_soft_deletes_matching_session():
	"""Test delete_session marks deleted_on rather than removing the row, when org/username/connection_key all match"""

	with step("Arrange: A session scoped to TESTDB/bob."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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

	with step("Assert: The row still exists with deleted_on set, not removed."):
		assert response.status_code == 204
		session.refresh_from_db()
		assert session.deleted_on is not None


def test_sessions_excludes_soft_deleted_session():
	"""Test sessions omits a soft-deleted session from the requesting user's listing"""

	with step(
		"Arrange: One active and one soft-deleted session, same org/username/connection_key."
	):
		org = _make_org()
		active = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MChatSession.objects.create(
			connection_key="TESTDB",
			deleted_on=timezone.now(),
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": active.project_id},
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: Only the active session is returned."):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [active.id]


def _make_callback_request(data, org, secret="test-secret"):
	"""Build a DRF-compatible n8n_callback POST request with a valid shared-secret header"""
	request = _factory.post("/", data, format="json", HTTP_X_N8N_SECRET=secret)
	request.get_org_slug = lambda: org.slug
	return request


def _run_usage_collection_synchronously(*args, **kwargs):
	"""threading.Thread side_effect: runs _collect_and_record_usage's own call inline instead of backgrounding it"""
	# threading.Thread is a single global class -- patching it outright would also break
	# asgiref.sync.async_to_sync's own internal thread pool, used earlier in the same
	# request (_resolve_and_persist_state). Only the call site under test (identified by
	# its target) is intercepted; every other call is handed to the real class unchanged.
	if kwargs.get("target") is _collect_and_record_usage:
		kwargs["target"](**(kwargs.get("kwargs") or {}))
		return MagicMock()
	return _REAL_THREAD(*args, **kwargs)  # pylint: disable=bad-thread-instantiation


def _make_usage_request(org, session, root_execution_id=None):
	"""Build an n8n_callback request for the usage-collection tests, optionally carrying root_execution_id"""
	data = {
		"group_name": "chat_1_bob_abc",
		"session_id": session.id,
		"text": "hi",
		"type": "agent",
	}
	if root_execution_id:
		data["root_execution_id"] = root_execution_id
	return _make_callback_request(data, org)


def test_n8n_callback_fires_background_usage_collection_when_root_execution_id_present(
	settings,
):
	"""Test n8n_callback persists a token_usage MUsageEvent once the (mocked) execution-tree walk resolves"""

	with step("Arrange: A session and a callback payload carrying root_execution_id."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_usage_request(org, session, root_execution_id="7530")

	with step(
		"Act: Call n8n_callback with the background thread forced synchronous "
		"and collect_execution_tree_usage mocked to a canned result."
	):
		with patch(
			"drf_api.resources.chat.main.threading.Thread",
			side_effect=_run_usage_collection_synchronously,
		), patch(
			"drf_api.resources.chat.main.collect_execution_tree_usage",
			return_value={
				"completion_tokens": 5,
				"prompt_tokens": 10,
				"total_tokens": 15,
			},
		) as mock_collect:
			response = VSChat.as_view(
				{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
			)(request)

	with step(
		"Assert: The walk was invoked with the payload's root_execution_id, and a "
		"token_usage event was recorded with the right identity and totals."
	):
		assert response.status_code == 200
		mock_collect.assert_called_once_with("7530")
		event = MUsageEvent.objects.get(event_type="token_usage", org=org)
		assert event.connection_key == "TESTDB"
		assert event.model_name == "gpt-5-mini"
		assert event.prompt_tokens == 10
		assert event.completion_tokens == 5
		assert event.total_tokens == 15
		assert event.username == "bob"


def test_n8n_callback_records_no_token_usage_event_when_tree_walk_finds_nothing(
	settings,
):
	"""Test n8n_callback creates no MUsageEvent when collect_execution_tree_usage resolves to None"""

	with step("Arrange: A session and a callback payload carrying root_execution_id."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_usage_request(org, session, root_execution_id="7530")

	with step(
		"Act: Call n8n_callback with collect_execution_tree_usage mocked to None "
		"(e.g. the tree never finished, or genuinely used no tokens)."
	):
		with patch(
			"drf_api.resources.chat.main.threading.Thread",
			side_effect=_run_usage_collection_synchronously,
		), patch(
			"drf_api.resources.chat.main.collect_execution_tree_usage",
			return_value=None,
		):
			response = VSChat.as_view(
				{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
			)(request)

	with step("Assert: No token_usage event was recorded."):
		assert response.status_code == 200
		assert not MUsageEvent.objects.filter(
			event_type="token_usage", org=org
		).exists()


def test_n8n_callback_skips_usage_collection_when_root_execution_id_absent(settings):
	"""Test n8n_callback never touches collect_execution_tree_usage when the payload carries no root_execution_id"""

	with step("Arrange: A session and a callback payload with no root_execution_id."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_usage_request(org, session)

	with step("Act: Call n8n_callback."):
		with patch(
			"drf_api.resources.chat.main.collect_execution_tree_usage"
		) as mock_collect:
			response = VSChat.as_view(
				{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
			)(request)

	with step("Assert: The execution tree was never queried, no event was recorded."):
		assert response.status_code == 200
		mock_collect.assert_not_called()
		assert not MUsageEvent.objects.filter(org=org).exists()


def test_n8n_callback_records_process_execution_event(settings):
	"""Test n8n_callback persists a process_execution MUsageEvent when processes is present"""

	with step(
		"Arrange: A session and a callback payload carrying a disambiguation list."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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
		"Arrange: A session and a callback payload carrying an active intention node "
		"with a numeric process_id but no disambiguation list."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_def",
				"session_id": session.id,
				"state": {
					"active_node_id": "n1",
					"intention_nodes": {
						"n1": {
							"id": "n1",
							"process_definition": {"name": "Create Purchase Request"},
							"process_id": 1,
						}
					},
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
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
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


def test_n8n_callback_reset_process_clears_active_node_id(settings):
	"""Test n8n_callback honours reset_process=True for active_node_id, clearing it instead of keeping the stale value"""

	with step(
		"Arrange: A session with an active_node_id already persisted in Redis state."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		group_name = f"chat_reset_node_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"active_node_id": "n1",
					"intention_nodes": {"n1": {"id": "n1", "status": "active"}},
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
				"state": {"active_node_id": None, "reset_process": True},
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


def test_n8n_callback_persists_intention_nodes(settings):
	"""Test n8n_callback persists intention_nodes and falls back to the current value when omitted"""

	with step(
		"Arrange: A session and a first callback carrying intention-graph fields."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		group_name = f"chat_nodes_{session.id}_{uuid4()}"
		first_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {
					"intention_nodes": {"n1": {"id": "n1", "status": "paused"}},
				},
				"text": "step 1",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			first_request
		)

	with step("Act: Send a second callback that omits intention_nodes entirely."):
		second_request = _make_callback_request(
			{
				"group_name": group_name,
				"session_id": session.id,
				"state": {"active_node_id": "n1"},
				"text": "step 2",
				"type": "agent",
			},
			org,
		)
		VSChat.as_view({"post": "n8n_callback"}, permission_classes=[PN8nCallback])(
			second_request
		)

	with step("Assert: The previously persisted intention_nodes survive untouched."):
		session.refresh_from_db()
		assert session.n8n_state["intention_nodes"] == {
			"n1": {"id": "n1", "status": "paused"}
		}


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


def test_n8n_callback_persists_message_for_soft_deleted_session(settings):
	"""Test n8n_callback still persists a message against a soft-deleted session -- an in-flight
	execution fired before the user deleted the chat must still be able to write its result back"""

	with step(
		"Arrange: A soft-deleted session and a callback payload referencing its id."
	):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			deleted_on=timezone.now(),
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_callback_request(
			{
				"group_name": "chat_soft_deleted_session",
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
		"Assert: 200 is returned and the message was persisted against the session."
	):
		assert response.status_code == 200
		assert MChatMessage.objects.filter(session=session, text="hi").exists()


def test_n8n_callback_rejects_a_field_it_does_not_declare(settings):
	"""Test n8n_callback rejects a payload carrying a field SN8nCallback doesn't declare"""

	with step("Arrange: A session and a callback payload carrying a bogus extra key."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_abc",
				"session_id": session.id,
				"some_future_debug_field": {"anything": "at all"},
				"text": "hi",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step("Assert: The request was rejected, nothing was persisted."):
		assert response.status_code == 400
		assert not MChatMessage.objects.filter(session=session).exists()


def test_n8n_callback_rejects_malformed_session_id(settings):
	"""Test n8n_callback returns 400 when session_id isn't the integer SN8nCallback expects"""

	with step("Arrange: A callback payload with a non-numeric session_id."):
		settings.N8N_CALLBACK_SECRET = "test-secret"
		org = _make_org()
		request = _make_callback_request(
			{
				"group_name": "chat_1_bob_abc",
				"session_id": "not-a-number",
				"text": "hi",
				"type": "agent",
			},
			org,
		)

	with step("Act: Call n8n_callback."):
		response = VSChat.as_view(
			{"post": "n8n_callback"}, permission_classes=[PN8nCallback]
		)(request)

	with step("Assert: The request was rejected with a validation error."):
		assert response.status_code == 400


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
			"language": "es",
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
		assert sent_payload["language"] == "es"
		assert _pop_pending(group_name) is None


def test_release_and_refire_requeues_when_another_execution_started(mocker):
	"""Test _release_and_refire puts the message back if another execution grabbed the lock first"""

	with step(
		"Arrange: A pending message and try_start() mocked to report the lock as taken."
	):
		group_name = f"chat_test_{uuid4()}"
		pending = {
			"expertise_level": 2,
			"group_name": group_name,
			"message": "queued message",
		}
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
		pending = {
			"expertise_level": 2,
			"group_name": group_name,
			"message": "queued message",
		}
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
