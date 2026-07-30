"""This module contains tests for the chat resource connection_key scoping"""

# General imports
from urllib.parse import urlencode

# Lib imports
import pytest
from allure import step
from django.utils import timezone
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MChatMessage, MChatSession, MOrganization, MSeat, MUsageEvent
from drf_api.resources.chat.main import VSChat
from drf_api.resources.chat.permission import PN8nCallback

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
		event = MUsageEvent.objects.get(org=org, event_type="token_usage")
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
		event = MUsageEvent.objects.get(org=org, event_type="process_execution")
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
					"process_id": 1,
					"process_definition": {"name": "Create Purchase Request"},
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
		event = MUsageEvent.objects.get(org=org, event_type="process_execution")
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
