"""Seat capacity validator"""

# Lib imports
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.models import MSeat


class VSeatCapacityAvailable:  # pylint: disable=too-few-public-methods
	"""Validates that an org has at least one unused seat and returns the org."""

	# Callers are expected to pass an org instance already locked via
	# select_for_update() within an open transaction, so the count below is
	# race-safe against concurrent seat provisioning for the same org.

	def __init__(self, error_msg="SEAT_LIMIT_EXCEEDED"):
		"""Constructor."""
		self.error_msg = error_msg

	def __call__(self, org):
		"""Raise SEAT_LIMIT_EXCEEDED when the org has no remaining seat capacity."""
		active_count = MSeat.objects.filter(org=org, status="active").count()
		if active_count >= org.seat_limit:
			raise ValidationError(self.error_msg)
		return org
