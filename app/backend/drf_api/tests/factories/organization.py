"""Organization factory"""

# Lib imports
import factory
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MOrganization


class FOrganization(DjangoModelFactory):
	"""Factory for MOrganization"""

	class Meta:
		model = MOrganization

	integration = factory.LazyFunction(dict)
	name = factory.Faker("company")
	plan = factory.LazyFunction(dict)
	seat_limit = 0
	slug = factory.Sequence(lambda n: f"org-{n}")
