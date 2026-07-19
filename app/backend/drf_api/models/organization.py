"""Organization model"""

# Lib imports
from django.core.exceptions import ValidationError
from django.db import models

# App imports
from drf_api.models.base import MBase
from drf_api.models.fields import EncryptedJSONField

# The organization slug is resolved from the first label of the request host
# (see MOrganizationMiddleware). "orb" is the first label of the bare
# orb.darchsystems.com domain, so it must never be assignable to a real
# organization or the marketing/sign-up page would resolve as that tenant.
RESERVED_ORG_SLUGS = {
	"admin",
	"api",
	"app",
	"assets",
	"cdn",
	"ftp",
	"mail",
	"orb",
	"static",
	"www",
}


def _validate_slug_not_reserved(value):
	"""Raises ValidationError when the slug is reserved."""
	if value.lower() in RESERVED_ORG_SLUGS:
		raise ValidationError("RESERVED_ORG_SLUG")


class MOrganization(MBase):
	"""Organization model"""

	integration = EncryptedJSONField(default=dict)
	name = models.CharField(
		blank=False,
		db_index=True,
		max_length=40,
		null=False,
	)
	seat_limit = models.PositiveIntegerField(default=0)
	slug = models.CharField(
		blank=False,
		db_index=True,
		max_length=40,
		null=False,
		unique=True,
		validators=[_validate_slug_not_reserved],
	)

	# Date times
	created_on = models.DateTimeField(auto_now_add=True)

	@classmethod
	def get_by_slug(cls, slug: str, frontend_base: str = None):
		"""Look up an org by slug. Returns (org, None) or (None, error_str)."""
		try:
			return cls.objects.get(slug=slug), None
		except cls.DoesNotExist:
			error = (
				f"{frontend_base}/?error=ORGANIZATION_NOT_FOUND"
				if frontend_base
				else None
			)
			return None, error

	def safe_to_dict(self) -> dict:
		"""Return dict representation of the organization with secrets stripped from integration."""
		# n8n legitimately reads auth_driver/base_url/target and other config from this
		# blob, but the XSUAA client_secret must never leave the backend.
		data = self.to_dict()
		data["integration"] = {
			key: value
			for key, value in dict(self.integration).items()
			if key != "client_secret"
		}
		return data

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.slug}"

	class Meta:
		app_label = "drf_api"
		ordering = ["-created_on"]
