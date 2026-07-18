"""VAuthenticatorExist validator"""

# Lib imports
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.resources.auth.factory import FAuthenticator


class VAuthenticatorExist:  # pylint: disable=too-few-public-methods
	"""Validates that a given driver key is registered in FAuthenticator."""

	def __init__(self, error_msg="NOT_VALID_AUTH_DRIVER"):
		"""Constructor."""
		self.error_msg = error_msg

	def __call__(self, driver, integration=None):
		"""Raises ValidationError when the driver key is unknown."""
		try:
			return FAuthenticator.get_instance(driver=driver, integration=integration)
		except Exception as error:
			raise ValidationError(self.error_msg) from error
