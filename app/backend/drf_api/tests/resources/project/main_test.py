"""This module contains tests for the project resource viewset"""

# General imports
from datetime import timedelta
from urllib.parse import urlencode

# Lib imports
import pytest
from allure import step
from django.utils import timezone
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.models import MChatSession, MOrganization, MProject, MSeat
from drf_api.resources.project.main import VSProject

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance with an active seat for bob and alice"""
	org = MOrganization.objects.create(name=slug, slug=slug)
	MSeat.objects.create(org=org, status="active", username="bob")
	MSeat.objects.create(org=org, status="active", username="alice")
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


def _make_session(org, project, **extra):
	"""Create a persisted MChatSession inside a project (bob on TESTDB)"""
	return MChatSession.objects.create(
		connection_key="TESTDB", org=org, project=project, username="bob", **extra
	)


def _call(action_map, request, **kwargs):
	"""Dispatch a request to VSProject bound to the given {method: action} map"""
	return VSProject.as_view(action_map)(request, **kwargs)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_only_the_requesters_live_projects_with_active_session_counts():
	"""Test list is identity-scoped, hides soft-deleted projects, and counts only live sessions"""

	with step("Arrange: Live/deleted/foreign projects and live/deleted sessions."):
		org = _make_org()
		mine = _make_project(org, name="Mine")
		_make_project(org, name="Deleted", deleted_on=timezone.now())
		_make_project(org, name="Alice's", username="alice")
		_make_project(org, name="Other db", connection_key="OTHERDB")
		_make_session(org, mine)
		_make_session(org, mine)
		_make_session(org, mine, deleted_on=timezone.now())
		request = _make_request("get", org)

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: Only Mine is returned, paginated, with 2 active sessions."):
		assert response.status_code == 200
		assert response.data["count"] == 1
		assert response.data["results"][0]["name"] == "Mine"
		assert response.data["results"][0]["chat_sessions_count"] == 2


def test_list_defaults_to_most_recently_accessed_first():
	"""Test list orders by accessed_on descending when no ordering is asked for"""

	with step("Arrange: Three projects with staggered accessed_on."):
		org = _make_org()
		now = timezone.now()
		for index, name in enumerate(["Oldest", "Middle", "Newest"]):
			project = _make_project(org, name=name)
			MProject.objects.filter(pk=project.pk).update(
				accessed_on=now + timedelta(minutes=index)
			)
		request = _make_request("get", org)

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: Newest first."):
		assert [row["name"] for row in response.data["results"]] == [
			"Newest",
			"Middle",
			"Oldest",
		]


@pytest.mark.parametrize(
	"payload",
	[
		{"expected": ["A", "B", "C"], "ordering": "name"},
		{"expected": ["C", "B", "A"], "ordering": "-name"},
		{"expected": ["B", "C", "A"], "ordering": "chat_sessions_count"},
		{"expected": ["A", "C", "B"], "ordering": "-chat_sessions_count"},
	],
)
def test_list_orders_by_the_requested_field(payload):
	"""Test list sorts by name and by the annotated chat_sessions_count, both directions"""

	with step(
		f"Arrange: A has 3 sessions, C has 1, B has 0; ordering={payload['ordering']}."
	):
		org = _make_org()
		project_a = _make_project(org, name="A")
		_make_project(org, name="B")
		project_c = _make_project(org, name="C")
		for _ in range(3):
			_make_session(org, project_a)
		_make_session(org, project_c)
		request = _make_request("get", org, query={"ordering": payload["ordering"]})

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: Rows come back in the requested order."):
		assert [row["name"] for row in response.data["results"]] == payload["expected"]


@pytest.mark.parametrize(
	"payload",
	[
		{"expected": ["Second", "First"], "ordering": "summary"},
		{"expected": ["First", "Second"], "ordering": "-summary"},
	],
)
def test_list_orders_by_summary(payload):
	"""Test list sorts by summary, so the management table's summary column sorter really sorts"""

	with step(
		f"Arrange: Two projects with different summaries; ordering={payload['ordering']}."
	):
		org = _make_org()
		_make_project(org, name="First", summary="zzz")
		_make_project(org, name="Second", summary="aaa")
		request = _make_request("get", org, query={"ordering": payload["ordering"]})

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: Rows come back in summary order."):
		assert [row["name"] for row in response.data["results"]] == payload["expected"]


def test_list_paginates_with_limit_and_offset():
	"""Test list honors limit/offset and reports the full count"""

	with step("Arrange: Five projects."):
		org = _make_org()
		for index in range(5):
			_make_project(org, name=f"P{index}")
		request = _make_request(
			"get", org, query={"limit": 2, "offset": 2, "ordering": "name"}
		)

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: The middle page is returned, with the full count."):
		assert response.data["count"] == 5
		assert [row["name"] for row in response.data["results"]] == ["P2", "P3"]


def test_list_filters_by_name():
	"""Test list applies the shared table component's name__icontains filter"""

	with step("Arrange: Two projects, one matching."):
		org = _make_org()
		_make_project(org, name="Client Alpha")
		_make_project(org, name="Internal")
		request = _make_request("get", org, query={"name__icontains": "alpha"})

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: Only the matching project is returned."):
		assert [row["name"] for row in response.data["results"]] == ["Client Alpha"]


def test_list_is_empty_when_identity_resolves_to_nothing(mocker):
	"""Test list defensively returns nothing when the view resolves no identity, instead of an unscoped queryset"""

	with step(
		"Arrange: A project, and a view whose own identity lookup comes back blank."
	):
		# The permission class resolves identity on its own (not through the view), so
		# the seat check still passes and only get_queryset() sees the blank identity.
		org = _make_org()
		_make_project(org)
		request = _make_request("get", org)
		mocker.patch.object(VSProject, "_get_org_and_user", return_value=(None, "", ""))

	with step("Act: Call list."):
		response = _call({"get": "list"}, request)

	with step("Assert: An empty page is returned."):
		assert response.status_code == 200
		assert response.data["count"] == 0


# ---------------------------------------------------------------------------
# create / update
# ---------------------------------------------------------------------------


def test_create_stamps_the_requesters_identity_and_ignores_client_supplied_fields():
	"""Test create sets org/username/connection_key server-side and can never create a Default project"""

	with step(
		"Arrange: A create payload that tries to smuggle in identity and is_default."
	):
		org = _make_org()
		request = _make_request(
			"post",
			org,
			data={
				"connection_key": "OTHERDB",
				"is_default": True,
				"name": "Work",
				"summary": "Client work",
				"username": "alice",
			},
		)

	with step("Act: Call create."):
		response = _call({"post": "create"}, request)

	with step(
		"Assert: The project belongs to bob/TESTDB and is not a Default project."
	):
		assert response.status_code == 201
		project = MProject.objects.get(pk=response.data["id"])
		assert (project.username, project.connection_key) == ("bob", "TESTDB")
		assert project.org_id == org.id
		assert project.is_default is False
		assert project.summary == "Client work"
		assert response.data["chat_sessions_count"] == 0


def test_create_rejects_a_blank_name():
	"""Test create answers 400 with a name error for a blank name"""

	with step("Arrange: A payload with a blank name."):
		org = _make_org()
		request = _make_request("post", org, data={"name": ""})

	with step("Act: Call create."):
		response = _call({"post": "create"}, request)

	with step("Assert: A 400 is returned, flagging the name."):
		assert response.status_code == 400
		assert response.data["errors"][0]["attr"] == "name"


def test_update_renames_a_regular_project():
	"""Test update lets a regular project be renamed and re-summarised"""

	with step("Arrange: A regular project."):
		org = _make_org()
		project = _make_project(org)
		request = _make_request(
			"patch", org, data={"name": "Renamed", "summary": "New"}
		)

	with step("Act: Call partial_update."):
		response = _call({"patch": "partial_update"}, request, pk=project.id)

	with step(
		"Assert: The project was updated, with its session count still annotated."
	):
		assert response.status_code == 200
		project.refresh_from_db()
		assert (project.name, project.summary) == ("Renamed", "New")
		assert response.data["chat_sessions_count"] == 0


def test_update_refuses_to_rename_the_default_project():
	"""Test update blocks a Default-project rename server-side, however the client sends it"""

	with step("Arrange: The Default project and a rename request."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		request = _make_request("patch", org, data={"name": "Renamed"})

	with step("Act: Call partial_update."):
		response = _call({"patch": "partial_update"}, request, pk=default.id)

	with step("Assert: A 400 names the problem, and the name is unchanged."):
		assert response.status_code == 400
		assert response.data["errors"] == [
			{
				"attr": "name",
				"code": "invalid",
				"detail": "Default project cannot be renamed.",
			}
		]
		default.refresh_from_db()
		assert default.name == "Default"


@pytest.mark.parametrize(
	"data",
	[
		{"summary": "Notes about the default"},
		{"name": "Default", "summary": "Same name"},
	],
)
def test_update_allows_editing_the_default_projects_summary(data):
	"""Test the Default project's summary stays editable, including when the unchanged name is sent along"""

	with step(f"Arrange: The Default project and an update of {sorted(data)}."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		request = _make_request("patch", org, data=data)

	with step("Act: Call partial_update."):
		response = _call({"patch": "partial_update"}, request, pk=default.id)

	with step("Assert: The summary was saved, the name left alone."):
		assert response.status_code == 200
		default.refresh_from_db()
		assert default.summary == data["summary"]
		assert default.name == "Default"


@pytest.mark.parametrize(
	"payload",
	[
		{
			"action_map": {"patch": "partial_update"},
			"data": {"name": "X"},
			"method": "patch",
		},
		{"action_map": {"delete": "destroy"}, "data": None, "method": "delete"},
		{"action_map": {"post": "select"}, "data": None, "method": "post"},
		{"action_map": {"post": "empty"}, "data": None, "method": "post"},
	],
)
@pytest.mark.parametrize(
	"foreign",
	[
		{
			"connection_key": "TESTDB",
			"description": "another user's",
			"username": "alice",
		},
		{
			"connection_key": "OTHERDB",
			"description": "another connection_key's",
			"username": "bob",
		},
		{
			"connection_key": "TESTDB",
			"deleted_on": timezone.now(),
			"description": "a soft-deleted",
			"username": "bob",
		},
	],
)
def test_detail_actions_404_for_projects_the_requester_cannot_see(payload, foreign):
	"""Test update/destroy/select/empty all 404 (and change nothing) for someone else's or a deleted project"""

	with step(f"Arrange: {foreign['description']} project."):
		org = _make_org()
		extra = {key: value for key, value in foreign.items() if key != "description"}
		project = _make_project(org, name="Untouchable", **extra)
		_make_session(org, project)
		request = _make_request(payload["method"], org, data=payload["data"])

	with step("Act: Call the detail action."):
		response = _call(payload["action_map"], request, pk=project.id)

	with step("Assert: A 404 is returned and nothing changed."):
		assert response.status_code == 404
		project.refresh_from_db()
		assert project.name == "Untouchable"
		assert project.chat_sessions.filter(deleted_on__isnull=True).count() == 1


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------


def test_destroy_soft_deletes_an_empty_project():
	"""Test destroy marks deleted_on and answers 204 for a project with no live sessions"""

	with step("Arrange: A project whose only session is already soft-deleted."):
		org = _make_org()
		project = _make_project(org)
		_make_session(org, project, deleted_on=timezone.now())
		request = _make_request("delete", org)

	with step("Act: Call destroy."):
		response = _call({"delete": "destroy"}, request, pk=project.id)

	with step("Assert: 204, and the row is kept but marked deleted."):
		assert response.status_code == 204
		project.refresh_from_db()
		assert project.deleted_on is not None


def test_destroy_refuses_the_default_project():
	"""Test destroy answers 400 in the shape the shared table component reads, and keeps the Default project"""

	with step("Arrange: The Default project."):
		org = _make_org()
		default = MProject.get_or_create_default(org, "bob", "TESTDB")
		request = _make_request("delete", org)

	with step("Act: Call destroy."):
		response = _call({"delete": "destroy"}, request, pk=default.id)

	with step(
		"Assert: A 400 {errors: [{attr, detail}]} is returned and the project survives."
	):
		assert response.status_code == 400
		assert response.data["errors"] == [
			{
				"attr": "id",
				"code": "invalid",
				"detail": "Default project cannot be deleted.",
			}
		]
		default.refresh_from_db()
		assert default.deleted_on is None


def test_destroy_refuses_a_project_with_active_sessions_until_it_is_emptied():
	"""Test the delete-blocked-until-empty flow: destroy 400s, empty clears the sessions, destroy then succeeds"""

	with step("Arrange: A project with one live chat session."):
		org = _make_org()
		project = _make_project(org)
		session = _make_session(org, project)

	with step("Act: Try to destroy it, empty it, then destroy it again."):
		blocked = _call(
			{"delete": "destroy"}, _make_request("delete", org), pk=project.id
		)
		emptied = _call({"post": "empty"}, _make_request("post", org), pk=project.id)
		deleted = _call(
			{"delete": "destroy"}, _make_request("delete", org), pk=project.id
		)

	with step(
		"Assert: Blocked first, then the session is soft-deleted and the project goes."
	):
		assert blocked.status_code == 400
		assert blocked.data["errors"] == [
			{
				"attr": "id",
				"code": "invalid",
				"detail": "Project still has active chat sessions.",
			}
		]
		assert emptied.status_code == 200
		assert emptied.data["chat_sessions_count"] == 0
		session.refresh_from_db()
		assert session.deleted_on is not None
		assert deleted.status_code == 204
		project.refresh_from_db()
		assert project.deleted_on is not None


# ---------------------------------------------------------------------------
# default / select / empty
# ---------------------------------------------------------------------------


def test_default_creates_the_default_project_on_first_use_and_reuses_it():
	"""Test default returns the requester's locked Default project, creating it lazily exactly once"""

	with step("Arrange: A user with no projects."):
		org = _make_org()

	with step("Act: Call default twice."):
		first = _call({"get": "default"}, _make_request("get", org))
		second = _call({"get": "default"}, _make_request("get", org))

	with step("Assert: The same locked Default project came back both times."):
		assert first.status_code == 200
		assert first.data["is_default"] is True
		assert first.data["name"] == "Default"
		assert first.data["id"] == second.data["id"]
		assert MProject.objects.count() == 1


def test_select_marks_the_project_as_just_accessed():
	"""Test select moves a project to the front of the most-recently-accessed ordering"""

	with step(
		"Arrange: Two projects, the one to select being the least recently accessed."
	):
		org = _make_org()
		target = _make_project(org, name="Target")
		other = _make_project(org, name="Other")
		now = timezone.now()
		MProject.objects.filter(pk=target.pk).update(
			accessed_on=now - timedelta(days=2)
		)
		MProject.objects.filter(pk=other.pk).update(accessed_on=now - timedelta(days=1))

	with step("Act: Call select on the target, then list."):
		selected = _call({"post": "select"}, _make_request("post", org), pk=target.id)
		listed = _call({"get": "list"}, _make_request("get", org))

	with step("Assert: The target is returned and now sorts first."):
		assert selected.status_code == 200
		assert selected.data["id"] == target.id
		assert [row["name"] for row in listed.data["results"]] == ["Target", "Other"]


def test_empty_soft_deletes_only_this_projects_live_sessions():
	"""Test empty clears the project's live sessions and leaves every other project's sessions alone"""

	with step("Arrange: Two live sessions here, one in another project."):
		org = _make_org()
		project = _make_project(org, name="Target")
		other = _make_project(org, name="Other")
		_make_session(org, project)
		_make_session(org, project)
		untouched = _make_session(org, other)
		request = _make_request("post", org)

	with step("Act: Call empty."):
		response = _call({"post": "empty"}, request, pk=project.id)

	with step(
		"Assert: This project reports 0 sessions, and the other project's is intact."
	):
		assert response.status_code == 200
		assert response.data["chat_sessions_count"] == 0
		assert project.chat_sessions.filter(deleted_on__isnull=True).count() == 0
		untouched.refresh_from_db()
		assert untouched.deleted_on is None
