"""This module contains tests for AStorage's abstract-method enforcement"""

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.storage.driver.abstract import AStorage


class _MissingUpload(AStorage):
	"""Concrete driver missing upload() — used to prove partial implementations can't instantiate."""

	def delete(self, dest_path: str) -> None:
		"""Unused by this test."""

	def presigned_url(self, dest_path: str, expires_in: int) -> str:
		"""Unused by this test."""


class _FullDriver(AStorage):
	"""Concrete driver implementing the full contract — used to prove a complete driver can instantiate."""

	def delete(self, dest_path: str) -> None:
		"""Unused by this test."""

	def presigned_url(self, dest_path: str, expires_in: int) -> str:
		"""Unused by this test."""

	def upload(self, src_path: str, dest_path: str, content_type: str) -> None:
		"""Unused by this test."""


def test_abstract_cannot_be_instantiated_directly():
	"""Test AStorage itself cannot be instantiated — it declares no concrete delete()/presigned_url()/upload()"""

	with step("Act & Assert: Instantiating AStorage raises TypeError."):
		with pytest.raises(TypeError):
			AStorage()  # pylint: disable=abstract-class-instantiated


def test_partial_driver_cannot_be_instantiated():
	"""Test a driver missing one abstract method still cannot be instantiated"""

	with step(
		"Act & Assert: Instantiating a driver missing upload() raises TypeError."
	):
		with pytest.raises(TypeError):
			_MissingUpload()  # pylint: disable=abstract-class-instantiated


def test_full_driver_can_be_instantiated():
	"""Test a driver implementing both abstract methods instantiates cleanly"""

	with step("Act: Instantiate a fully-implemented driver."):
		driver = _FullDriver()

	with step("Assert: The instance is an AStorage."):
		assert isinstance(driver, AStorage)
