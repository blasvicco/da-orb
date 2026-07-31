"""Session proxy factory"""

# General imports
import secrets
from datetime import timedelta

# Lib imports
import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MSessionProxy
from drf_api.tests.factories.organization import FOrganization


class FSessionProxy(DjangoModelFactory):
	"""Factory for MSessionProxy"""

	class Meta:
		model = MSessionProxy

	auth_driver = "b1s"
	connection_key = factory.Faker("word")
	credentials = factory.LazyFunction(dict)
	expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=24))
	org = factory.SubFactory(FOrganization)
	token = factory.LazyFunction(lambda: secrets.token_urlsafe(32))
	username = factory.Faker("user_name")
