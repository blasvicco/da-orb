"""Custom password validators"""

# General imports
import re

# Lib imports
from django.core.exceptions import ValidationError


# pylint: disable=too-few-public-methods
class VNonAlphanumericPassword:
	"""Password validator non alphanumeric is required"""

	def validate(self, password, _):
		"""Validate that at least one non alphanumeric is being use"""
		matches = re.match(r".*[^a-zA-Z\d\s].*", password)
		if not matches:
			raise ValidationError("NON_ALPHANUMERIC_IS_REQUIRED")
