"""This module contains tests for the VAuthenticatorExist validator"""

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.validators import VAuthenticatorExist


def test_returns_the_driver_instance_for_a_known_driver():
	"""Test VAuthenticatorExist returns the driver instance for a registered driver key"""

	with step("Act: Call VAuthenticatorExist with the 'open_id' driver."):
		result = VAuthenticatorExist()(
			driver="open_id",
			integration={
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
			},
		)

	with step("Assert: A driver instance is returned."):
		assert result is not None


def test_raises_for_an_unknown_driver():
	"""Test VAuthenticatorExist raises NOT_VALID_AUTH_DRIVER for an unregistered driver key"""

	with step("Act/Assert: Call VAuthenticatorExist with an unknown driver key."):
		with pytest.raises(ValidationError, match="NOT_VALID_AUTH_DRIVER"):
			VAuthenticatorExist()(driver="not-a-real-driver")


def test_custom_error_msg():
	"""Test VAuthenticatorExist raises the constructor-provided error_msg instead of the default"""

	with step("Act/Assert: Call VAuthenticatorExist with a custom error_msg."):
		with pytest.raises(ValidationError, match="CUSTOM_CODE"):
			VAuthenticatorExist(error_msg="CUSTOM_CODE")(driver="not-a-real-driver")
