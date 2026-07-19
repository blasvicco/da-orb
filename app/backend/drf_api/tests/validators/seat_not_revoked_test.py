"""This module contains tests for the VSeatNotRevoked validator"""

# General imports
from types import SimpleNamespace

# Lib imports
import pytest
from allure import step
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.validators import VSeatNotRevoked


def test_returns_the_seat_when_active():
	"""Test VSeatNotRevoked passes through an active seat unchanged"""

	with step("Arrange: A seat stand-in with status='active'."):
		seat = SimpleNamespace(status="active")

	with step("Act: Call VSeatNotRevoked."):
		result = VSeatNotRevoked()(seat)

	with step("Assert: The same seat is returned."):
		assert result is seat


def test_raises_seat_revoked_when_revoked():
	"""Test VSeatNotRevoked raises SEAT_REVOKED for a revoked seat"""

	with step("Arrange: A seat stand-in with status='revoked'."):
		seat = SimpleNamespace(status="revoked")

	with step("Act/Assert: VSeatNotRevoked raises SEAT_REVOKED."):
		with pytest.raises(ValidationError, match="SEAT_REVOKED"):
			VSeatNotRevoked()(seat)
