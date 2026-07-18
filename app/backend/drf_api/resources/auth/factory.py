"""Authenticator factory"""

# General imports
import importlib

# Constants
INSTANCES = {}


# pylint: disable=too-few-public-methods
class FAuthenticator:
	"""Authenticator factory"""

	@staticmethod
	def get_instance(driver=None, integration=None):
		"""Factory instantiation — loads driver module dynamically and caches the class."""
		if not INSTANCES.get(driver):
			driver_module = importlib.import_module(
				f".driver.{driver}",
				__name__.replace(".factory", ""),
			)
			INSTANCES[driver] = driver_module.Instance
		return INSTANCES[driver](integration or {})
