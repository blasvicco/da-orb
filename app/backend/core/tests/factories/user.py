"""User factory"""

# Lib imports
import factory
from django.contrib.auth.models import User  # pylint: disable=imported-auth-user
from factory.django import DjangoModelFactory


class FUser(DjangoModelFactory):
	"""Factory for django.contrib.auth.models.User"""

	class Meta:
		model = User
		skip_postgeneration_save = True

	email = factory.Faker("email")
	first_name = factory.Faker("first_name")
	is_active = True
	last_name = factory.Faker("last_name")
	password = factory.PostGenerationMethodCall("set_password", "some!pass#12345")
	username = factory.Faker("user_name")
