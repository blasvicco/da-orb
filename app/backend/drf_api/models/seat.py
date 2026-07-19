"""Named-seat licensing model"""

# Lib imports
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.organization import MOrganization


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

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.org.slug}:{self.username}:{self.status}"
