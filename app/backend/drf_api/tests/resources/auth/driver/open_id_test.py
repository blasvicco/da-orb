"""This module contains tests for the Open ID authentication driver"""

# General imports
from unittest.mock import MagicMock

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.auth.driver.abstract import AuthDriverError
from drf_api.resources.auth.driver.open_id import Instance


def test_login_not_supported():
	"""Test login raises METHOD_NOT_ALLOWED since Open ID has no credential-based login"""

	with step("Arrange: An Open ID driver instance and a dummy request."):
		driver = Instance(
			{
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "id",
				"client_secret": "secret",
			}
		)
		request = MagicMock()

	with step("Act/Assert: login raises METHOD_NOT_ALLOWED."):
		with pytest.raises(AuthDriverError, match="METHOD_NOT_ALLOWED") as exc_info:
			driver.login(request, org="acme")

	with step("Assert: The error carries a 405 status code."):
		assert exc_info.value.status_code == 405
