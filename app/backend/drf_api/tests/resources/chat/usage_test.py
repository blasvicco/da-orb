"""This module contains tests for the chat resource's background token usage recording"""

# General imports
from unittest.mock import patch

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MChatSession, MOrganization, MProject, MUsageEvent
from drf_api.resources.chat.main import _collect_and_record_usage

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def test_collect_and_record_usage_records_nothing_when_the_session_no_longer_exists():
	"""Test _collect_and_record_usage drops the usage instead of failing when the chat session vanished meanwhile"""

	with step(
		"Arrange: A session that is hard-deleted while the tree walk was polling."
	):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=org,
			project=MProject.get_or_create_default(org, "bob", "TESTDB"),
			username="bob",
		)
		session_id = session.id
		MChatSession.objects.filter(id=session_id).delete()

	with step(
		"Act: Call _collect_and_record_usage with a canned execution-tree result."
	):
		with patch(
			"drf_api.resources.chat.main.collect_execution_tree_usage",
			return_value={
				"completion_tokens": 5,
				"prompt_tokens": 10,
				"total_tokens": 15,
			},
		) as mock_collect:
			_collect_and_record_usage(
				process_name="Purchase Request",
				root_execution_id="7530",
				session_id=session_id,
			)

	with step("Assert: The tree was walked, but no token_usage event was recorded."):
		mock_collect.assert_called_once_with("7530")
		assert not MUsageEvent.objects.filter(
			event_type="token_usage", org=org
		).exists()
