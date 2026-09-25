"""This module contains tests for the chat resource's project support: project-scoped sessions and recent"""

# General imports
from datetime import timedelta
from urllib.parse import urlencode

# Lib imports
import pytest
from allure import step
from django.db import connection
from django.test.utils import CaptureQueriesContext
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
from drf_api.resources.chat.main import VSChat

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


def _make_project(org, name="Work", username="bob", connection_key="TESTDB", **extra):
	"""Create a persisted (non-default) MProject for the given identity"""
	return MProject.objects.create(
		connection_key=connection_key,
		name=name,
		org=org,
		username=username,
		**extra,
	)


@pytest.mark.parametrize(
	"query",
	[
		{"description": "no project_id", "params": None},
		{"description": "empty project_id", "params": {"project_id": ""}},
		{"description": "non-numeric project_id", "params": {"project_id": "abc"}},
	],
)
def test_sessions_returns_empty_list_without_a_valid_project_id(query):
	"""Test sessions requires project_id: an absent or garbled one is an empty list, never an unfiltered match"""

	with step(
		f"Arrange: A session exists, but the request has {query['description']}."
	):
		org = _make_org()
		MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query=query["params"],
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: An empty list is returned."):
		assert response.status_code == 200
		assert response.data == []


def test_sessions_scoped_by_project():
	"""Test sessions returns only the requested project's sessions, tagged with their project"""

	with step("Arrange: Sessions in two different projects of the same identity."):
		org = _make_org()
		work = _make_project(org, name="Work")
		matching = MChatSession.objects.create(
			connection_key="TESTDB", org=org, project=work, username="bob"
		)
		MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": work.id},
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: Only the requested project's session is returned."):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [matching.id]
		assert response.data[0]["project"] == work.id
		assert response.data[0]["project_name"] == "Work"


def test_sessions_are_newest_first():
	"""Test sessions lists a project's chats by updated_on descending, not in arbitrary aggregate-query order"""

	with step(
		"Arrange: Three sessions whose recency order differs from their creation order."
	):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		now = timezone.now()
		created = [
			MChatSession.objects.create(
				connection_key="TESTDB", org=org, project=project, username="bob"
			)
			for _ in range(3)
		]
		# created[0] newest, created[1] oldest, created[2] in between.
		for session, age in zip(created, [0, 2, 1]):
			MChatSession.objects.filter(pk=session.pk).update(
				updated_on=now - timedelta(days=age)
			)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": project.id},
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: Newest first."):
		assert [row["id"] for row in response.data] == [
			created[0].id,
			created[2].id,
			created[1].id,
		]


def _add_chat(org, project, message_types=()):
	"""Create a chat in the project holding the given message types in order, plus one token_usage event"""
	session = MChatSession.objects.create(
		connection_key="TESTDB", org=org, project=project, username="bob"
	)
	now = timezone.now()
	for index, message_type in enumerate(message_types):
		MChatMessage.objects.create(
			session=session,
			text=message_type,
			timestamp=now + timedelta(seconds=index),
			type=message_type,
		)
	MUsageEvent.objects.create(
		connection_key="TESTDB",
		event_type="token_usage",
		occurred_on=now,
		org=org,
		session=session,
		total_tokens=10,
		username="bob",
	)
	return session


def _list_chats(action, org, project):
	"""Call sessions/recent as bob, returning the response and every SQL statement it issued"""
	query = {"project_id": project.id} if action == "sessions" else None
	request = _make_request(
		"get", org, connection_key="TESTDB", query=query, username="bob"
	)
	with CaptureQueriesContext(connection) as captured:
		response = VSChat.as_view({"get": action})(request)
	return response, [entry["sql"] for entry in captured.captured_queries]


@pytest.mark.parametrize("action", ["sessions", "recent"])
def test_listing_chats_costs_the_same_queries_however_many_chats(action):
	"""Test sessions/recent fetch every chat's data in one query, not one extra query per chat"""

	with step("Arrange: One chat, and the number of queries listing it takes."):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		_add_chat(org, project, ["user", "agent"])
		_, baseline = _list_chats(action, org, project)

	with step(
		"Act: Add twelve more chats (answered, pending and empty) and list again."
	):
		for index in range(12):
			_add_chat(org, project, [["user"], ["user", "agent"], []][index % 3])
		response, many = _list_chats(action, org, project)

	with step(
		"Assert: Same number of queries, and the chat table is read exactly once."
	):
		assert len(response.data) == (13 if action == "sessions" else 3)
		assert len(many) == len(baseline)
		assert len([sql for sql in many if '"drf_api_mchatsession"' in sql]) == 1


def test_sessions_pending_flag_follows_the_last_message():
	"""Test pending is true only when a chat's newest message is the user's, across the annotated single query"""

	with step(
		"Arrange: Chats ending on a user message, an agent reply, a follow-up, and empty."
	):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		waiting = _add_chat(org, project, ["user"])
		answered = _add_chat(org, project, ["user", "agent"])
		followed_up = _add_chat(org, project, ["user", "agent", "user"])
		empty = _add_chat(org, project, [])

	with step("Act: List the project's chats."):
		response, _ = _list_chats("sessions", org, project)

	with step("Assert: Only the chats whose last message is the user's are pending."):
		pending = {row["id"]: row["pending"] for row in response.data}
		assert pending == {
			waiting.id: True,
			answered.id: False,
			followed_up.id: True,
			empty.id: False,
		}
		assert all(row["tokens_used"] == 10 for row in response.data)


def test_sessions_returns_at_most_fifty():
	"""Test sessions caps the project-scoped list at the 50 most-recent sessions"""

	with step("Arrange: 51 sessions in one project."):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		MChatSession.objects.bulk_create(
			[
				MChatSession(
					connection_key="TESTDB", org=org, project=project, username="bob"
				)
				for _ in range(51)
			]
		)
		request = _make_request(
			"get",
			org,
			connection_key="TESTDB",
			query={"project_id": project.id},
			username="bob",
		)

	with step("Act: Call sessions."):
		response = VSChat.as_view({"get": "sessions"})(request)

	with step("Assert: Only 50 rows are returned."):
		assert response.status_code == 200
		assert len(response.data) == 50


def test_recent_returns_three_latest_across_projects():
	"""Test recent returns the 3 most-recently-updated live sessions across every project, newest first"""

	with step(
		"Arrange: Five sessions over two projects, one soft-deleted, with staggered updated_on."
	):
		org = _make_org()
		work = _make_project(org, name="Work")
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		now = timezone.now()
		sessions = []
		for index, project in enumerate([default, work, default, work, work]):
			session = MChatSession.objects.create(
				connection_key="TESTDB", org=org, project=project, username="bob"
			)
			MChatSession.objects.filter(pk=session.pk).update(
				updated_on=now + timedelta(minutes=index)
			)
			sessions.append(session)
		MChatSession.objects.filter(pk=sessions[4].pk).update(deleted_on=now)
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call recent."):
		response = VSChat.as_view({"get": "recent"})(request)

	with step(
		"Assert: The three newest live sessions come back, each with its project name."
	):
		assert response.status_code == 200
		assert [row["id"] for row in response.data] == [
			sessions[3].id,
			sessions[2].id,
			sessions[1].id,
		]
		assert [row["project_name"] for row in response.data] == [
			"Work",
			"Default",
			"Work",
		]


def test_recent_excludes_other_identities():
	"""Test recent never leaks another user's or another connection_key's sessions"""

	with step(
		"Arrange: One session each for bob/TESTDB, alice/TESTDB and bob/OTHERDB."
	):
		org = _make_org()
		mine = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "alice", "TESTDB"),
			username="alice",
		)
		MChatSession.objects.create(
			connection_key="OTHERDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "OTHERDB"),
			username="bob",
		)
		request = _make_request("get", org, connection_key="TESTDB", username="bob")

	with step("Act: Call recent."):
		response = VSChat.as_view({"get": "recent"})(request)

	with step("Assert: Only bob's TESTDB session is returned."):
		assert [row["id"] for row in response.data] == [mine.id]


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "no org", "has_org": False, "username": ""},
		{"description": "an org but a blank username", "has_org": True, "username": ""},
	],
)
def test_recent_returns_empty_list_when_identity_resolves_differently_mid_request(
	mocker, payload
):
	"""Test recent defensively returns an empty list, never an unfiltered match, when it has no usable identity"""

	with step(
		f"Arrange: A valid request, but identity resolution yields {payload['description']}."
	):
		org = _make_org()
		MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request("get", org, connection_key="TESTDB", username="bob")
		mocker.patch.object(
			VSChat,
			"_get_org_and_user",
			return_value=(org if payload["has_org"] else None, payload["username"], ""),
		)

	with step("Act: Call recent."):
		response = VSChat.as_view({"get": "recent"})(request)

	with step("Assert: An empty list is returned without error."):
		assert response.status_code == 200
		assert response.data == []


@pytest.mark.parametrize(
	"action_name, method",
	[("messages", "get"), ("delete_session", "delete")],
)
def test_soft_deleted_session_is_gone_for_messages_and_delete(action_name, method):
	"""Test messages and delete_session both 404 for an already soft-deleted session"""

	with step(f"Arrange: A soft-deleted session, and a {action_name} request for it."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			deleted_on=timezone.now(),
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		request = _make_request(
			method,
			org,
			connection_key="TESTDB",
			query={"session_id": session.id},
			username="bob",
		)

	with step(f"Act: Call {action_name}."):
		response = VSChat.as_view({method: action_name})(request)

	with step("Assert: A 404 is returned."):
		assert response.status_code == 404
