"""Credential-proxy session model"""

# General imports
import secrets
from datetime import timedelta

# Lib imports
from django.db import models
from django.utils import timezone

# App imports
from drf_api.models.base import MBase
from drf_api.models.fields import EncryptedJSONField
from drf_api.models.organization import MOrganization

SESSION_PROXY_IDLE_TIMEOUT = timedelta(hours=24)


class MSessionProxy(MBase):
	"""Server-side proxy for an auth driver's credential session, shared across drivers."""

	# The browser only ever holds the opaque token; the real driver credentials
	# stay encrypted server-side and are handed to n8n at fire time. `auth_driver`
	# identifies which driver issued the row, so one table serves every driver
	# that needs credential proxying instead of a table per driver.

	auth_driver = models.CharField(db_index=True, max_length=20)
	org = models.ForeignKey(
		MOrganization,
		on_delete=models.CASCADE,
		related_name="session_proxies",
	)
	username = models.CharField(max_length=150, db_index=True)
	connection_key = models.CharField(max_length=150)
	token = models.CharField(max_length=64, unique=True, db_index=True)
	credentials = EncryptedJSONField(default=dict)
	issued_on = models.DateTimeField(auto_now_add=True)
	last_active_on = models.DateTimeField(auto_now=True)
	expires_at = models.DateTimeField(db_index=True)

	class Meta:
		app_label = "drf_api"
		indexes = [
			models.Index(
				fields=["org", "username", "connection_key"],
				name="session_proxy_org_user_key_idx",
			)
		]

	@classmethod
	def issue(cls, *, auth_driver, connection_key, org, password, username):
		"""Create a new proxy session for already-validated credentials and return it."""
		return cls.objects.create(
			auth_driver=auth_driver,
			connection_key=connection_key,
			credentials={"password": password, "username": username},
			expires_at=timezone.now() + SESSION_PROXY_IDLE_TIMEOUT,
			org=org,
			token=secrets.token_urlsafe(32),
			username=username,
		)

	def __str__(self):
		"""To string method"""
		return f"{self.id}:{self.org.slug}:{self.auth_driver}:{self.username}"
