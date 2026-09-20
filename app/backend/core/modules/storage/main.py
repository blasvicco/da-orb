"""Storage module"""

# General imports
import importlib

# Constants
INSTANCES = {}


# pylint: disable=too-few-public-methods
class FStorage:
	"""Storage driver factory"""

	@staticmethod
	def get_instance(driver=None):
		"""Factory instantiation — loads the driver module dynamically and caches the instance."""
		if not INSTANCES.get(driver):
			driver_module = importlib.import_module(
				f".driver.{driver}",
				__name__.replace(".main", ""),
			)
			INSTANCES[driver] = driver_module.Instance()
		return INSTANCES[driver]
