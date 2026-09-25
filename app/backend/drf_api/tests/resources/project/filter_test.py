"""This module contains tests for the project resource filters"""

# General imports
from datetime import UTC, datetime

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization, MProject
from drf_api.resources.project.filter import DFProject

pytestmark = pytest.mark.django_db


def _make_projects():
	"""Create two projects, one created late in the evening of 2026-03-10 and one on 2026-03-12"""
	org = MOrganization.objects.create(name="acme", slug="acme")
	evening = MProject.objects.create(
		connection_key="TESTDB",
		name="Evening",
		org=org,
		summary="alpha",
		username="bob",
	)
	later = MProject.objects.create(
		connection_key="TESTDB", name="Later", org=org, summary="beta", username="bob"
	)
	MProject.objects.filter(pk=evening.pk).update(
		created_on=datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
	)
	MProject.objects.filter(pk=later.pk).update(
		created_on=datetime(2026, 3, 12, 8, 0, tzinfo=UTC)
	)
	return evening, later


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "lte bound includes the whole of that day",
			"expected": ["Evening"],
			"params": {"created_on__lte": "2026-03-10"},
		},
		{
			"description": "gte bound includes the whole of that day",
			"expected": ["Evening", "Later"],
			"params": {"created_on__gte": "2026-03-10"},
		},
		{
			"description": "gte bound after the evening one excludes it",
			"expected": ["Later"],
			"params": {"created_on__gte": "2026-03-11"},
		},
		{
			"description": "a same-day range still matches",
			"expected": ["Evening"],
			"params": {
				"created_on__gte": "2026-03-10",
				"created_on__lte": "2026-03-10",
			},
		},
		{
			"description": "name icontains is case-insensitive",
			"expected": ["Later"],
			"params": {"name__icontains": "LAT"},
		},
		{
			"description": "summary icontains matches",
			"expected": ["Evening"],
			"params": {"summary__icontains": "alph"},
		},
		{
			"description": "no params returns everything",
			"expected": ["Evening", "Later"],
			"params": {},
		},
	],
)
def test_filters(payload):
	"""Test DFProject filters by name/summary text and by calendar-day datetime bounds"""

	with step(f"Arrange: Two projects; {payload['description']}."):
		_make_projects()

	with step("Act: Filter the project queryset."):
		queryset = DFProject(payload["params"], queryset=MProject.objects.all()).qs

	with step("Assert: The expected projects match."):
		assert sorted(project.name for project in queryset) == payload["expected"]
