"""Usage event factory"""

# Lib imports
import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MUsageEvent
from drf_api.tests.factories.organization import FOrganization


class FUsageEvent(DjangoModelFactory):
	"""Factory for MUsageEvent"""

	class Meta:
		model = MUsageEvent

	completion_tokens = None
	connection_key = factory.Faker("word")
	event_type = "token_usage"
	model_name = "gpt-4"
	occurred_on = factory.LazyFunction(timezone.now)
	org = factory.SubFactory(FOrganization)
	process_name = ""
	prompt_tokens = None
	session = None
	total_tokens = None
	username = factory.Faker("user_name")
