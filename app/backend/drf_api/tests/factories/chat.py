"""Chat session and message factories"""

# Lib imports
import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MChatMessage, MChatSession
from drf_api.tests.factories.organization import FOrganization
from drf_api.tests.factories.project import FProject


class FChatSession(DjangoModelFactory):
	"""Factory for MChatSession"""

	class Meta:
		model = MChatSession

	connection_key = factory.Faker("word")
	n8n_state = None
	org = factory.SubFactory(FOrganization)
	# Same identity as the session itself, like a project resolved through MProject.resolve_for_chat.
	project = factory.SubFactory(
		FProject,
		connection_key=factory.SelfAttribute("..connection_key"),
		org=factory.SelfAttribute("..org"),
		username=factory.SelfAttribute("..username"),
	)
	title = factory.Faker("sentence")
	username = factory.Faker("user_name")


class FChatMessage(DjangoModelFactory):
	"""Factory for MChatMessage"""

	class Meta:
		model = MChatMessage

	extra = None
	session = factory.SubFactory(FChatSession)
	text = factory.Faker("sentence")
	timestamp = factory.LazyFunction(timezone.now)
	type = "user"
