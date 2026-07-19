"""Seat not-revoked validator"""

# Lib imports
from rest_framework.exceptions import ValidationError


class VSeatNotRevoked:  # pylint: disable=too-few-public-methods
	"""Validates that a seat has not been revoked and returns it."""

	def __init__(self, error_msg="SEAT_REVOKED"):
		"""Constructor."""
		self.error_msg = error_msg

	def __call__(self, seat):
		"""Raise SEAT_REVOKED when the seat's status is revoked."""
		if seat.status == "revoked":
			raise ValidationError(self.error_msg)
		return seat
