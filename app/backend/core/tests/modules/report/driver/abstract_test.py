"""This module contains tests for AReport's abstract-method enforcement"""

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.report.driver.abstract import AReport


# pylint: disable=too-few-public-methods
class _FullDriver(AReport):
	"""Concrete driver implementing the full contract — used to prove a complete driver can instantiate."""

	def render(self, template_path: str, data: dict) -> str:
		"""Unused by this test."""


def test_abstract_cannot_be_instantiated_directly():
	"""Test AReport itself cannot be instantiated — it declares no concrete render()"""

	with step("Act & Assert: Instantiating AReport raises TypeError."):
		with pytest.raises(TypeError):
			AReport()  # pylint: disable=abstract-class-instantiated


def test_full_driver_can_be_instantiated():
	"""Test a driver implementing render() instantiates cleanly"""

	with step("Act: Instantiate a fully-implemented driver."):
		driver = _FullDriver()

	with step("Assert: The instance is an AReport."):
		assert isinstance(driver, AReport)
