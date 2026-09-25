"""This module contains tests for the chat resource serializers"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.chat.serializer import SChatSession


@pytest.mark.parametrize(
	"payload",
	[
		{"description": "the user spoke last", "last": "user", "expected": True},
		{"description": "the agent replied last", "last": "agent", "expected": False},
		{
			"description": "a system message is last",
			"last": "system",
			"expected": False,
		},
		{"description": "the chat has no messages", "last": None, "expected": False},
	],
)
def test_get_pending_reads_the_last_message_annotation(payload):
	"""Test pending is derived purely from the last_message_type annotation, with no query of its own"""

	with step(f"Arrange: A chat row annotated as if {payload['description']}."):
		row = SimpleNamespace(last_message_type=payload["last"])

	with step("Act: Compute pending."):
		result = SChatSession().get_pending(row)

	with step("Assert: Only a user message last means pending."):
		assert result is payload["expected"]


def test_get_pending_requires_the_annotation():
	"""Test an unannotated row fails loudly instead of quietly falling back to a query per chat"""

	with step("Arrange: A row without the last_message_type annotation."):
		row = SimpleNamespace()

	with step("Act and assert: Computing pending raises."):
		with pytest.raises(AttributeError):
			SChatSession().get_pending(row)


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "a summed annotation",
			"attrs": {"tokens_used": 40},
			"expected": 40,
		},
		{
			"description": "a null annotation",
			"attrs": {"tokens_used": None},
			"expected": 0,
		},
		{"description": "no annotation", "attrs": {}, "expected": 0},
	],
)
def test_get_tokens_used_defaults_to_zero(payload):
	"""Test tokens_used reads its annotation, defaulting to 0 when absent or null"""

	with step(f"Arrange: A row with {payload['description']}."):
		row = SimpleNamespace(**payload["attrs"])

	with step("Act: Compute tokens_used."):
		result = SChatSession().get_tokens_used(row)

	with step("Assert: Result matches expectation."):
		assert result == payload["expected"]
