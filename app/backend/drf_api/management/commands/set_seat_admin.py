"""Django command to grant org-admin access to an existing seat"""

# Lib imports
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

# App imports
from drf_api.models import MOrganization
from drf_api.resources.auth.helpers import set_org_admin
from drf_api.validators import VSeatExists


class Command(BaseCommand):
	"""Command class"""

	help = "Grant org-admin access to an existing seat"

	def add_arguments(self, parser):
		"""Add arguments"""
		parser.add_argument("org_slug", help="Organization slug", type=str)
		parser.add_argument(
			"username", help="SAP username of the existing seat", type=str
		)

	def handle(self, *args, **options):
		"""Validate the org and seat exist, then grant org-admin access"""
		org_slug = options["org_slug"]
		username = options["username"]

		try:
			org = MOrganization.objects.get(slug=org_slug)
		except MOrganization.DoesNotExist as error:
			raise CommandError(
				f"No organization found with slug '{org_slug}'"
			) from error

		try:
			VSeatExists()(org, username)
		except ValidationError as error:
			raise CommandError(
				f"No seat found for '{username}' in org '{org_slug}'"
			) from error

		set_org_admin(org, username, True)
		self.stdout.write(
			self.style.SUCCESS(f"'{username}' is now an org-admin for '{org_slug}'")
		)
