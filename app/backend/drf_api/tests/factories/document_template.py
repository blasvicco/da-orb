"""Document template factory"""

# Lib imports
import factory
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MDocumentTemplate
from drf_api.tests.factories.organization import FOrganization


class FDocumentTemplate(DjangoModelFactory):
	"""Factory for MDocumentTemplate"""

	class Meta:
		model = MDocumentTemplate

	document_type = "invoice"
	name = factory.Faker("word")
	org = factory.SubFactory(FOrganization)
