"""Named-seat licensing model"""

# Lib imports
from django.db import models, transaction

# App imports
from drf_api.models.base import MBase
from drf_api.models.organization import MOrganization
from drf_api.validators import VSeatCapacityAvailable, VSeatExists, VSeatNotRevoked

class MSeat(MBase):
	"""One named license seat consumed by a SAP username within an org."""

	# Independent of which company database/connection they use, and
	# independent of org-admin role.

	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="seats",
	)
	username = models.CharField(max_length=150, db_index=True)
	status = models.CharField(
		max_length=10,
		choices=[("active", "Active"), ("revoked", "Revoked")],
		default="active",
		db_index=True,
	)
	granted_on = models.DateTimeField(auto_now_add=True)
	revoked_on = models.DateTimeField(null=True, blank=True)
	revoked_by = models.CharField(max_length=150, blank=True, default="")

	class Meta:
		app_label = "drf_api"
		constraints = [
			models.UniqueConstraint(
				fields=["org", "username"], name="uniq_seat_org_username"
			)
		]

	@classmethod
	def has_active_seat(cls, org, username) -> bool:
		"""Return True if the given username currently holds an active seat in the org."""
		return cls.objects.filter(org=org, username=username, status="active").exists()

	@classmethod
	@transaction.atomic
	def provision_or_check_seat(cls, org, username):
		"""Provision a new seat if capacity allows, or validate an existing one."""

		# Returns the seat. Raises ValidationError (SEAT_LIMIT_EXCEEDED or SEAT_REVOKED)
		# on failure. Locks the org row so two simultaneous first-logins racing the
		# last seat can't both succeed.

		org_locked = MOrganization.objects.select_for_update().get(pk=org.pk)
		seat = cls.objects.filter(org=org_locked, username=username).first()
		if seat is None:
			VSeatCapacityAvailable()(org_locked)
			return cls.objects.create(
				org=org_locked,
				status="active",
				username=username,
			)
		return VSeatNotRevoked()(seat)

	@classmethod
	@transaction.atomic
	def reinstate_seat(cls, org, username):
		"""Reinstate a previously revoked seat if capacity allows."""

		# Returns the seat. Raises ValidationError (SEAT_NOT_FOUND or SEAT_LIMIT_EXCEEDED)
		# on failure. Uses the same org-row locking as provision_or_check_seat, so an
		# admin can't reinstate past a since-lowered seat_limit even under concurrent
		# requests.

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

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.org.slug}:{self.username}:{self.status}"
