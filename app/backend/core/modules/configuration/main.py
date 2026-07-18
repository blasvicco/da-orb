"""Configuration module that loads settings from different backends"""

# General imports
import importlib
import os

# pylint: disable=too-few-public-methods
class ConfigurationError(Exception):
	"""Configuration Error Exception"""


class Configuration:
	"""Configuration class"""

	__data = {}

	def __init__(self):
		"""Initialize the configuration by delegating to the appropriate driver."""
		driver = os.environ.get("CFG_DRIVER")
		try:
			module = importlib.import_module(
				f"core.modules.configuration.driver.{driver}"
			)
		except ModuleNotFoundError as error:
			raise ConfigurationError(f"Driver {driver} not found.") from error
		self.__data = module.load()

	def get(self):
		"""Retrieve a value using dot-notation."""
		return self.__data
