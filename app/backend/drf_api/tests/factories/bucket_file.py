"""Bucket file factory"""

# Lib imports
import factory
from factory.django import DjangoModelFactory

# App imports
from drf_api.models import MBucketFile
from drf_api.tests.factories.chat import FChatSession


class FBucketFile(DjangoModelFactory):
	"""Factory for MBucketFile"""

	class Meta:
		model = MBucketFile

	description = ""
	mime_type = "text/csv"
	name = factory.Faker("file_name", extension="csv")
	origin = "user_upload"
	session = factory.SubFactory(FChatSession)
	size = factory.Faker("random_int", min=1, max=1000000)
	storage_path = factory.LazyAttribute(
		lambda obj: f"{obj.session.org.slug}/{obj.session.connection_key}/session/{obj.session.id}/placeholder_{obj.name}"
	)
