"""This module contains tests for the FReport driver factory"""

# General imports
from unittest.mock import MagicMock, patch

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.report.main import FReport, INSTANCES


@pytest.fixture(autouse=True)
def reset_instances():
	"""Reset INSTANCES cache before and after each test to avoid state leakage"""
	INSTANCES.clear()
	yield
	INSTANCES.clear()


@pytest.mark.parametrize(
	"payload",
	[
		{
			"cached": False,
			"description": "first call imports the driver and returns a new instance",
		},
		{
			"cached": True,
			"description": "second call returns the cached instance without re-importing",
		},
	],
)
def test_get_instance(payload):
	"""Test FReport.get_instance returns a new or cached instance correctly"""

	with step(f"Arrange: {payload['description']}"):
		mock_instance = MagicMock()
		mock_module = MagicMock()
		mock_module.Instance.return_value = mock_instance
		driver = "rpt_rs"

		if payload["cached"]:
			INSTANCES[driver] = mock_instance

	with step("Act: Call get_instance."):
		with patch(
			"core.modules.report.main.importlib.import_module",
			return_value=mock_module,
		) as mock_import:
			result = FReport.get_instance(driver)

	with step("Assert: Correct instance returned and import called only when needed."):
		assert result == mock_instance
		if payload["cached"]:
			mock_import.assert_not_called()
		else:
			mock_import.assert_called_once_with(".driver.rpt_rs", "core.modules.report")
			assert INSTANCES[driver] == mock_instance


def test_get_instance_unknown_driver_raises():
	"""Test FReport.get_instance propagates ModuleNotFoundError for an unregistered driver"""

	with step("Arrange: A driver name with no matching module."):
		driver = "nonexistent_driver"

	with step("Act & Assert: get_instance raises ModuleNotFoundError."):
		with pytest.raises(ModuleNotFoundError):
			FReport.get_instance(driver)
