"""Named-seat licensing helpers"""

# Lib imports
from django.db import transaction

# App imports
from drf_api.models import MOrganization, MSeat
from drf_api.validators import VSeatCapacityAvailable, VSeatExists, VSeatNotRevoked


def has_active_seat(org, username) -> bool:
	"""Return True if the given username currently holds an active seat in the org."""
	return MSeat.objects.filter(org=org, username=username, status="active").exists()


def provision_or_check_seat(org, username):
	"""Provision a new seat if capacity allows, or validate an existing one."""

	# Returns the seat. Raises ValidationError (SEAT_LIMIT_EXCEEDED or SEAT_REVOKED)
	# on failure. Locks the org row so two simultaneous first-logins racing the
	# last seat can't both succeed.
	with transaction.atomic():
		org_locked = MOrganization.objects.select_for_update().get(pk=org.pk)
		seat = MSeat.objects.filter(org=org_locked, username=username).first()
		if seat is None:
			VSeatCapacityAvailable()(org_locked)
			return MSeat.objects.create(
				org=org_locked,
				status="active",
				username=username,
			)
		return VSeatNotRevoked()(seat)


def reinstate_seat(org, username):
	"""Reinstate a previously revoked seat if capacity allows."""

	# Returns the seat. Raises ValidationError (SEAT_NOT_FOUND or SEAT_LIMIT_EXCEEDED)
	# on failure. Uses the same org-row locking as provision_or_check_seat, so an
	# admin can't reinstate past a since-lowered seat_limit even under concurrent
	# requests.
	with transaction.atomic():
		org_locked = MOrganization.objects.select_for_update().get(pk=org.pk)
		seat = VSeatExists()(org_locked, username)
		if seat.status == "active":
			return seat
		VSeatCapacityAvailable()(org_locked)
		seat.revoked_by = ""
		seat.revoked_on = None
		seat.status = "active"
		seat.save()
		return seat
