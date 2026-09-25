"""Project factory"""

# Lib imports
import factory
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MProject
from drf_api.tests.factories.organization import FOrganization


class FProject(DjangoModelFactory):
	"""Factory for MProject"""

	class Meta:
		model = MProject

	connection_key = factory.Faker("word")
	is_default = False
	name = factory.Faker("word")
	org = factory.SubFactory(FOrganization)
	summary = factory.Faker("sentence")
	username = factory.Faker("user_name")
