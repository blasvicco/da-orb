"""This module contains tests for the chat session list serializer"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MChatSession, MOrganization, MProject
from drf_api.resources.chat_session.serializer import SChatSessionItem

pytestmark = pytest.mark.django_db


def _make_chat():
	"""Create a persisted chat in a project"""
	org = MOrganization.objects.create(name="acme", slug="acme")
	project = MProject.objects.create(
		connection_key="TESTDB", name="Work", org=org, username="bob"
	)
	return MChatSession.objects.create(
		connection_key="TESTDB", org=org, project=project, title="Hi", username="bob"
	)


def test_exposes_only_the_table_columns():
	"""Test a row carries the list's columns and never the chat's n8n state or messages"""

	with step("Arrange: A chat annotated with its token total, as VSChatSession does."):
		chat = _make_chat()
		chat.tokens_used = 12

	with step("Act: Serialize it."):
		data = SChatSessionItem(chat).data

	with step("Assert: Exactly the documented fields."):
		assert set(data) == {
			"created_on",
			"id",
			"project",
			"project_name",
			"title",
			"tokens_used",
			"updated_on",
		}
		assert (data["project_name"], data["tokens_used"]) == ("Work", 12)


def test_requires_the_token_annotation():
	"""Test an unannotated row fails loudly instead of quietly costing a query per row"""

	with step("Arrange: A chat without the tokens_used annotation."):
		chat = _make_chat()

	with step("Act and assert: Serializing raises."):
		with pytest.raises(AttributeError):
			_ = SChatSessionItem(chat).data
