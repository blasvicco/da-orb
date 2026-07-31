"""This module contains tests for the VNonAlphanumericPassword validator"""

# General imports
from contextlib import nullcontext

# Lib imports
import pytest
from allure import step
from django.core.exceptions import ValidationError

# App imports
from core.validators.password import VNonAlphanumericPassword


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "password containing a non-alphanumeric character",
			"password": "abc123!",
			"valid": True,
		},
		{
			"description": "purely alphanumeric password",
			"password": "abc123",
			"valid": False,
		},
		{
			"description": "whitespace does not count as non-alphanumeric",
			"password": "abc 123",
			"valid": False,
		},
	],
)
def test_validate(payload):
	"""Test VNonAlphanumericPassword.validate accepts/rejects passwords correctly"""

	with step(f"Arrange: {payload['description']}."):
		context = (
			nullcontext()
			if payload["valid"]
			else pytest.raises(ValidationError, match="NON_ALPHANUMERIC_IS_REQUIRED")
		)

	with step("Act: Call validate."):
		with context:
			VNonAlphanumericPassword().validate(payload["password"], None)
