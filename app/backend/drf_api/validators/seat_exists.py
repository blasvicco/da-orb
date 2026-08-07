"""Seat exists validator"""

# Lib imports
from rest_framework.exceptions import ValidationError

class VSeatExists:  # pylint: disable=too-few-public-methods
	"""Validates that a seat exists for the given org/username and returns it."""

	def __init__(self, error_msg="SEAT_NOT_FOUND"):
		"""Constructor."""
		self.error_msg = error_msg

	def __call__(self, org, username):
		"""Raise SEAT_NOT_FOUND when no seat row exists for this org/username."""
		# pylint: disable=import-outside-toplevel
		from drf_api.models import MSeat

		try:
			return MSeat.objects.get(org=org, username=username)
		except MSeat.DoesNotExist as error:
			raise ValidationError(self.error_msg) from error
