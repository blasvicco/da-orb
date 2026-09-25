"""This module contains tests for the chat session list filters"""

# General imports
from datetime import UTC, datetime

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MChatSession, MOrganization, MProject
from drf_api.resources.chat_session.filter import DFChatSession

pytestmark = pytest.mark.django_db


def _make_chats():
	"""Create two chats in two projects: one created late on 2026-03-10, one on 2026-03-12"""
	org = MOrganization.objects.create(name="acme", slug="acme")
	work = MProject.objects.create(
		connection_key="TESTDB", name="Work", org=org, username="bob"
	)
	home = MProject.objects.create(
		connection_key="TESTDB", name="Home", org=org, username="bob"
	)
	evening = MChatSession.objects.create(
		connection_key="TESTDB",
		org=org,
		project=work,
		title="Quarterly Report",
		username="bob",
	)
	later = MChatSession.objects.create(
		connection_key="TESTDB",
		org=org,
		project=home,
		title="Stock check",
		username="bob",
	)
	MChatSession.objects.filter(pk=evening.pk).update(
		created_on=datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
	)
	MChatSession.objects.filter(pk=later.pk).update(
		created_on=datetime(2026, 3, 12, 8, 0, tzinfo=UTC)
	)
	return work, home


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "title icontains is case-insensitive",
			"expected": ["Quarterly Report"],
			"params": {"title__icontains": "REPORT"},
		},
		{
			"description": "lte bound includes the whole of that day",
			"expected": ["Quarterly Report"],
			"params": {"created_on__lte": "2026-03-10"},
		},
		{
			"description": "gte bound after the evening one excludes it",
			"expected": ["Stock check"],
			"params": {"created_on__gte": "2026-03-11"},
		},
		{
			"description": "a same-day range still matches",
			"expected": ["Quarterly Report"],
			"params": {
				"created_on__gte": "2026-03-10",
				"created_on__lte": "2026-03-10",
			},
		},
		{
			"description": "no params returns everything",
			"expected": ["Quarterly Report", "Stock check"],
			"params": {},
		},
	],
)
def test_filters(payload):
	"""Test DFChatSession filters by title text and by calendar-day datetime bounds"""

	with step(f"Arrange: Two chats; {payload['description']}."):
		_make_chats()

	with step("Act: Filter the chat queryset."):
		queryset = DFChatSession(
			payload["params"], queryset=MChatSession.objects.all()
		).qs

	with step("Assert: The expected chats match."):
		assert sorted(chat.title for chat in queryset) == payload["expected"]


def test_project_id_filter():
	"""Test project_id narrows the list to one project's chats"""

	with step("Arrange: Two chats in two projects."):
		work, _ = _make_chats()

	with step("Act: Filter by the work project."):
		queryset = DFChatSession(
			{"project_id": work.id}, queryset=MChatSession.objects.all()
		).qs

	with step("Assert: Only its chat matches."):
		assert [chat.title for chat in queryset] == ["Quarterly Report"]
