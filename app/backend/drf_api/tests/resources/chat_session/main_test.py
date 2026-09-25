"""This module contains tests for the chat session list resource viewset"""

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
from drf_api.models import MChatSession, MOrganization, MProject, MSeat, MUsageEvent
from drf_api.resources.chat_session.main import VSChatSession

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an active seat for bob"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	MSeat.objects.create(org=org, status="active", username="bob")
	return org


def _make_request(method, org, data=None, query=None):
	"""Build a DRF-compatible request (bob on TESTDB) with org/auth headers already attached"""
	path = f"/?{urlencode(query)}" if query else "/"
	headers = {
		"HTTP_AUTHORIZATION": "Bearer sometoken",
		"HTTP_X_SAP_CONNECTION_KEY": "TESTDB",
		"HTTP_X_SAP_USERNAME": "bob",
	}
	if data is None:
		request = getattr(_factory, method)(path, **headers)
	else:
		request = getattr(_factory, method)(path, data, format="json", **headers)
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


def _make_chat(org, project, title="", tokens=None, **extra):
	"""Create a chat (bob on TESTDB) in a project, optionally with one token_usage event"""
	session = MChatSession.objects.create(
		**{
			"connection_key": "TESTDB",
			"org": org,
			"project": project,
			"title": title,
			"username": "bob",
			**extra,
		}
	)
	if tokens is not None:
		MUsageEvent.objects.create(
			connection_key="TESTDB",
			event_type="token_usage",
			occurred_on=timezone.now(),
			org=org,
			session=session,
			total_tokens=tokens,
			username="bob",
		)
	return session


def _list(org, query=None):
	"""Call list as bob"""
	return VSChatSession.as_view({"get": "list"})(
		_make_request("get", org, query=query)
	)


def _move(org, data):
	"""Call the bulk move as bob"""
	return VSChatSession.as_view({"post": "move"})(
		_make_request("post", org, data=data)
	)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_only_the_requesters_live_chats_as_lean_rows():
	"""Test list is identity-scoped, hides soft-deleted chats, paginates, and carries only the table's columns"""

	with step(
		"Arrange: Bob's live and deleted chats, plus another user's and another database's."
	):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		mine = _make_chat(org, project, title="Mine", tokens=15)
		_make_chat(org, project, title="Deleted", deleted_on=timezone.now())
		alice = MProject.get_or_create_default(org, "alice", "TESTDB")
		MChatSession.objects.create(
			connection_key="TESTDB", org=org, project=alice, username="alice"
		)
		other_db = MProject.get_or_create_default(org, "bob", "OTHERDB")
		MChatSession.objects.create(
			connection_key="OTHERDB", org=org, project=other_db, username="bob"
		)

	with step("Act: Call list."):
		response = _list(org)

	with step("Assert: Only Mine, paginated, with exactly the row fields."):
		assert response.status_code == 200
		assert response.data["count"] == 1
		row = response.data["results"][0]
		assert row["id"] == mine.id
		assert set(row) == {
			"created_on",
			"id",
			"project",
			"project_name",
			"title",
			"tokens_used",
			"updated_on",
		}
		assert (row["project"], row["project_name"], row["tokens_used"]) == (
			project.id,
			"Default",
			15,
		)


def test_list_can_be_narrowed_to_one_project():
	"""Test the project_id filter lists a single project's chats"""

	with step("Arrange: One chat in each of two projects."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		work = _make_project(org)
		_make_chat(org, default, title="In default")
		in_work = _make_chat(org, work, title="In work")

	with step("Act: List with project_id."):
		response = _list(org, {"project_id": work.id})

	with step("Assert: Only the work chat comes back."):
		assert [row["id"] for row in response.data["results"]] == [in_work.id]


def test_list_is_newest_first_by_default():
	"""Test list orders by updated_on descending when no ordering is asked for"""

	with step("Arrange: Three chats whose recency differs from their creation order."):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		now = timezone.now()
		chats = [_make_chat(org, project, title=name) for name in ("a", "b", "c")]
		for chat, age in zip(chats, [0, 2, 1]):
			MChatSession.objects.filter(pk=chat.pk).update(
				updated_on=now - timedelta(days=age)
			)

	with step("Act: List."):
		response = _list(org)

	with step("Assert: Newest first."):
		assert [row["title"] for row in response.data["results"]] == ["a", "c", "b"]


@pytest.mark.parametrize(
	"payload",
	[
		{"expected": ["A", "B", "C"], "ordering": "title"},
		{"expected": ["C", "B", "A"], "ordering": "-title"},
		{"expected": ["B", "C", "A"], "ordering": "tokens_used"},
		{"expected": ["A", "C", "B"], "ordering": "-tokens_used"},
	],
)
def test_list_orders_by_the_requested_column(payload):
	"""Test list sorts by title and by the token total (counting a chat with no usage as 0)"""

	with step(
		f"Arrange: A has 30 tokens, C has 5, B has none; ordering={payload['ordering']}."
	):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		_make_chat(org, project, title="A", tokens=30)
		_make_chat(org, project, title="B")
		_make_chat(org, project, title="C", tokens=5)

	with step("Act: List."):
		response = _list(org, {"ordering": payload["ordering"]})

	with step("Assert: Rows come back in the requested order."):
		assert [row["title"] for row in response.data["results"]] == payload["expected"]


def test_list_sums_only_token_usage_events():
	"""Test tokens_used adds up token_usage events and ignores other event types"""

	with step(
		"Arrange: A chat with two token_usage events and one process_execution event."
	):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		chat = _make_chat(org, project, tokens=15)
		for event_type, tokens in (("token_usage", 25), ("process_execution", None)):
			MUsageEvent.objects.create(
				connection_key="TESTDB",
				event_type=event_type,
				occurred_on=timezone.now(),
				org=org,
				session=chat,
				total_tokens=tokens,
				username="bob",
			)

	with step("Act: List."):
		response = _list(org)

	with step("Assert: 40 tokens."):
		assert response.data["results"][0]["tokens_used"] == 40


def test_list_paginates_with_limit_and_offset():
	"""Test list honors limit/offset and reports the full count"""

	with step("Arrange: Five chats."):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		for index in range(5):
			_make_chat(org, project, title=f"P{index}")

	with step("Act: Ask for the middle page, ordered by title."):
		response = _list(org, {"limit": 2, "offset": 2, "ordering": "title"})

	with step("Assert: The middle page comes back, with the full count."):
		assert response.data["count"] == 5
		assert [row["title"] for row in response.data["results"]] == ["P2", "P3"]


def test_list_costs_the_same_queries_however_many_chats():
	"""Test a page of chats is fetched in one query, not one extra query per chat"""

	with step("Arrange: One chat with usage, and the queries listing it takes."):
		org = _make_org()
		project = MProject.get_or_create_default(org, "bob", "TESTDB")
		_make_chat(org, project, tokens=10)
		with CaptureQueriesContext(connection) as baseline:
			_list(org, {"limit": 50})

	with step("Act: Add twelve more chats with usage and list again."):
		for _ in range(12):
			_make_chat(org, project, tokens=10)
		with CaptureQueriesContext(connection) as many:
			response = _list(org, {"limit": 50})

	with step(
		"Assert: Same number of queries, and the chat table is read once for the page."
	):
		assert len(response.data["results"]) == 13
		assert len(many) == len(baseline)


def test_list_is_empty_when_the_view_resolves_no_identity(mocker):
	"""Test list defensively returns nothing when the view resolves no identity, instead of an unscoped queryset"""

	with step(
		"Arrange: A chat, and a view whose own identity lookup comes back blank."
	):
		org = _make_org()
		_make_chat(org, MProject.get_or_create_default(org, "bob", "TESTDB"))
		mocker.patch.object(
			VSChatSession, "_get_org_and_user", return_value=(None, "", "")
		)

	with step("Act: List."):
		response = _list(org)

	with step("Assert: An empty page."):
		assert response.status_code == 200
		assert response.data["count"] == 0


# ---------------------------------------------------------------------------
# bulk move
# ---------------------------------------------------------------------------


def test_move_moves_every_selected_chat_and_only_those():
	"""Test move re-files the selected chats into the target project, leaving other chats and updated_on alone"""

	with step("Arrange: Three chats in Default; the first two are selected."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		target = _make_project(org, name="Target")
		first, second, unselected = (_make_chat(org, default) for _ in range(3))
		updated_on = MChatSession.objects.get(pk=first.pk).updated_on

	with step("Act: Move the two selected chats."):
		response = _move(
			org, {"project_id": target.id, "session_ids": [first.id, second.id]}
		)

	with step("Assert: Exactly those two moved, and their updated_on is untouched."):
		assert response.status_code == 200
		assert response.data == {"moved": 2, "project_id": target.id}
		assert MChatSession.objects.filter(project=target).count() == 2
		unselected.refresh_from_db()
		assert unselected.project_id == default.id
		first.refresh_from_db()
		assert first.updated_on == updated_on


def test_move_counts_a_repeated_id_once():
	"""Test duplicate ids in the selection don't inflate the count or fail the all-or-nothing check"""

	with step("Arrange: One chat, selected twice."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		target = _make_project(org, name="Target")
		chat = _make_chat(org, default)

	with step("Act: Move [id, id]."):
		response = _move(
			org, {"project_id": target.id, "session_ids": [chat.id, chat.id]}
		)

	with step("Assert: One chat moved."):
		assert response.status_code == 200
		assert response.data["moved"] == 1


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "another user's chat", "kwargs": {"username": "alice"}},
		{
			"description": "another database's chat",
			"kwargs": {"connection_key": "OTHERDB"},
		},
		{
			"description": "an already soft-deleted chat",
			"kwargs": {"deleted_on": timezone.now()},
		},
	],
)
def test_move_refuses_the_whole_selection_when_a_chat_is_not_the_requesters(payload):
	"""Test one foreign or deleted chat in the selection fails the entire move (404), moving nothing"""

	with step(
		f"Arrange: Bob's own chat plus {payload['description']}, and a target project."
	):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		target = _make_project(org, name="Target")
		mine = _make_chat(org, default)
		theirs = MChatSession.objects.create(
			**{
				"connection_key": "TESTDB",
				"org": org,
				"project": MProject.get_or_create_default(org, "alice", "TESTDB"),
				"username": "bob",
				**payload["kwargs"],
			}
		)

	with step("Act: Move both."):
		response = _move(
			org, {"project_id": target.id, "session_ids": [mine.id, theirs.id]}
		)

	with step("Assert: 404, and Bob's own chat did not move either."):
		assert response.status_code == 404
		assert (
			response.data["errors"][0]["detail"]
			== "Some of the selected chats no longer exist."
		)
		mine.refresh_from_db()
		assert mine.project_id == default.id


def test_move_refuses_a_chat_that_does_not_exist():
	"""Test an unknown id in the selection fails the whole move"""

	with step("Arrange: One real chat and one id that matches nothing."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		target = _make_project(org, name="Target")
		chat = _make_chat(org, default)

	with step("Act: Move both."):
		response = _move(
			org, {"project_id": target.id, "session_ids": [chat.id, 999999]}
		)

	with step("Assert: 404 and nothing moved."):
		assert response.status_code == 404
		chat.refresh_from_db()
		assert chat.project_id == default.id


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "another user's project", "kwargs": {"username": "alice"}},
		{
			"description": "another database's project",
			"kwargs": {"connection_key": "OTHERDB"},
		},
		{
			"description": "a soft-deleted project",
			"kwargs": {"deleted_on": timezone.now()},
		},
	],
)
def test_move_refuses_a_destination_the_requester_cannot_use(payload):
	"""Test a foreign or deleted destination project is a 404, and the chats stay where they are"""

	with step(f"Arrange: A chat and {payload['description']}."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		chat = _make_chat(org, default)
		target = _make_project(org, name="Target", **payload["kwargs"])

	with step("Act: Move the chat there."):
		response = _move(org, {"project_id": target.id, "session_ids": [chat.id]})

	with step("Assert: 404 naming the project, nothing moved."):
		assert response.status_code == 404
		assert (
			response.data["errors"][0]["detail"]
			== "The destination project no longer exists."
		)
		chat.refresh_from_db()
		assert chat.project_id == default.id


@pytest.mark.parametrize(
	"project_id",
	[None, 999999, "7", True, 1.5, [1]],
)
def test_move_refuses_a_missing_or_malformed_destination(project_id):
	"""Test an absent, unknown or non-integer project_id is a 404 rather than an error"""

	with step("Arrange: A chat to move."):
		org = _make_org()
		chat = _make_chat(org, MProject.get_or_create_default(org, "bob", "TESTDB"))

	with step("Act: Move it to a bad destination."):
		response = _move(org, {"project_id": project_id, "session_ids": [chat.id]})

	with step("Assert: 404."):
		assert response.status_code == 404


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "missing",
			"session_ids": "absent",
			"detail": "Chat ids must be a list of integers.",
		},
		{
			"description": "not a list",
			"session_ids": "5",
			"detail": "Chat ids must be a list of integers.",
		},
		{
			"description": "an empty list",
			"session_ids": [],
			"detail": "Select at least one chat.",
		},
		{
			"description": "non-integer entries",
			"session_ids": ["a"],
			"detail": "Chat ids must be a list of integers.",
		},
		{
			"description": "boolean entries",
			"session_ids": [True],
			"detail": "Chat ids must be a list of integers.",
		},
		{
			"description": "too many chats",
			"session_ids": list(range(1, 502)),
			"detail": "Too many chats selected.",
		},
	],
)
def test_move_validates_the_selection(payload):
	"""Test a bad session_ids payload is a 400 in the {errors: [{attr, detail}]} shape the table reads"""

	with step(
		f"Arrange: A target project and session_ids that are {payload['description']}."
	):
		org = _make_org()
		target = _make_project(org, name="Target")
		data = {"project_id": target.id}
		if payload["session_ids"] != "absent":
			data["session_ids"] = payload["session_ids"]

	with step("Act: Move."):
		response = _move(org, data)

	with step("Assert: A 400 on session_ids with the expected message."):
		assert response.status_code == 400
		error = response.data["errors"][0]
		assert (error["attr"], error["detail"]) == ("session_ids", payload["detail"])
