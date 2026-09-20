"""This module contains tests for the shared base permission"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.base_permission import BasePermission


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "no authenticated user",
			"expected": False,
			"user": None,
		},
		{
			"description": "an authenticated non-superuser",
			"expected": False,
			"user": SimpleNamespace(is_superuser=False),
		},
		{
			"description": "an authenticated superuser",
			"expected": True,
			"user": SimpleNamespace(is_superuser=True),
		},
	],
)
def test_base_permission_has_permission(payload):
	"""Test BasePermission only allows an authenticated superuser"""

	with step(f"Arrange: {payload['description']}."):
		request = SimpleNamespace(user=payload["user"])

	with step("Act: Call has_permission."):
		result = BasePermission().has_permission(request, None)

	with step("Assert: Result matches expected."):
		assert bool(result) is payload["expected"]
