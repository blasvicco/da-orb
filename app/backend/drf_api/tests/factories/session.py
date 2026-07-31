"""In-memory auth session factory"""

# Lib imports
import factory

# App imports
from drf_api.models import MSession


# pylint: disable-next=too-few-public-methods
class FSession(factory.Factory):
	"""Factory for the in-memory MSession (not a Django model)."""

	# pylint: disable-next=too-few-public-methods
	class Meta:
		"""Factory Boy configuration."""

		model = MSession

	access_token = factory.Faker("uuid4")
	database = "COMPANY_DB"
	expires_at = 0
	id_token = ""
	language = "es"
	org = "acme"
	refresh_token = ""
	user = factory.LazyFunction(lambda: {"password": "", "username": "bob"})
