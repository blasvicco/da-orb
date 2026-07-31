"""This module contains tests for the context permission"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.context.permission import PContext


@pytest.mark.parametrize(
	"payload",
	[
		{"action": "get", "description": "the get action is allowed", "expected": True},
		{
			"action": "list",
			"description": "any other action is denied",
			"expected": False,
		},
	],
)
def test_has_permission(payload):
	"""Test PContext only allows the get action"""

	with step(f"Arrange: {payload['description']}."):
		view = SimpleNamespace(action=payload["action"])

	with step("Act: Call has_permission."):
		result = PContext().has_permission(None, view)

	with step("Assert: Result matches expected."):
		assert result is payload["expected"]
