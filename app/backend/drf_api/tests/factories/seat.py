"""Seat factory"""

# Lib imports
import factory
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MSeat
from drf_api.tests.factories.organization import FOrganization


class FSeat(DjangoModelFactory):
	"""Factory for MSeat"""

	class Meta:
		model = MSeat

	org = factory.SubFactory(FOrganization)
	status = "active"
	username = factory.Faker("user_name")
