"""This module contains tests for the in-memory MSession auth session model"""

# Lib imports
from allure import step

# App imports
from drf_api.models import MSession


def test_defaults_when_constructed_without_kwargs():
	"""Test MSession applies its documented defaults when no kwargs are given"""

	with step("Arrange/Act: Construct MSession with no arguments."):
		session = MSession()

	with step("Assert: Defaults are applied, including a generated id_token."):
		assert session.access_token == ""
		assert session.database == ""
		assert session.expires_at == 0
		assert session.id_token != ""
		assert session.language == "es"
		assert session.org == ""
		assert session.refresh_token == ""
		assert session.user == {"password": "", "username": ""}


def test_user_falls_back_to_a_password_kwarg_with_an_empty_username():
	"""Test MSession builds a user dict from the password kwarg when user isn't given"""

	with step(
		"Arrange/Act: Construct MSession with a password kwarg but no user kwarg."
	):
		session = MSession(password="secret", username="bob")

	with step(
		"Assert: The fallback user dict carries the password but not the username."
	):
		assert session.user == {"password": "secret", "username": ""}


def test_connection_key_returns_database():
	"""Test MSession.connection_key exposes the database field"""

	with step("Arrange: A session with a database value."):
		session = MSession(database="SBODEMOUS")

	with step("Act: Read connection_key."):
		result = session.connection_key

	with step("Assert: It matches the database field."):
		assert result == "SBODEMOUS"


def test_to_dict_serialises_all_fields():
	"""Test MSession.to_dict returns a plain dict mirroring every field"""

	with step("Arrange: A fully populated session."):
		session = MSession(
			access_token="tok",
			database="SBODEMOUS",
			expires_at=123,
			id_token="idt",
			language="en",
			org="acme",
			refresh_token="ref",
			user={"password": "pw", "username": "bob"},
		)

	with step("Act: Call to_dict."):
		result = session.to_dict()

	with step("Assert: All fields are present."):
		assert result == {
			"access_token": "tok",
			"database": "SBODEMOUS",
			"expires_at": 123,
			"id_token": "idt",
			"language": "en",
			"org": "acme",
			"refresh_token": "ref",
			"user": {"password": "pw", "username": "bob"},
		}
