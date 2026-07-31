"""This module contains tests for the EncryptedJSONField custom model field"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization
from drf_api.models.fields.encrypted_json import EncryptedJSONField
from drf_api.tests.factories import FOrganization

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "an empty string returns an empty dict",
			"expected": {},
			"value": "",
		},
		{"description": "None returns an empty dict", "expected": {}, "value": None},
	],
)
def test_from_db_value_falsy(payload):
	"""Test from_db_value returns an empty dict for falsy stored values"""

	with step(f"Arrange: {payload['description']}."):
		field = EncryptedJSONField()

	with step("Act: Call from_db_value."):
		result = field.from_db_value(payload["value"], None, None)

	with step("Assert: An empty dict is returned."):
		assert result == payload["expected"]


def test_from_db_value_invalid_token_returns_empty_dict():
	"""Test from_db_value swallows decrypt/parse errors and returns an empty dict"""

	with step("Arrange: A value that is not a valid Fernet token."):
		field = EncryptedJSONField()

	with step("Act: Call from_db_value with garbage."):
		result = field.from_db_value("not-a-valid-token", None, None)

	with step("Assert: An empty dict is returned."):
		assert result == {}


def test_get_prep_value_defaults_none_to_empty_dict():
	"""Test get_prep_value treats None as an empty dict before encrypting"""

	with step("Arrange: A field instance."):
		field = EncryptedJSONField()

	with step("Act: Call get_prep_value with None."):
		encrypted = field.get_prep_value(None)

	with step("Assert: The encrypted token decrypts back to an empty dict."):
		assert field.from_db_value(encrypted, None, None) == {}


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "a dict value is returned unchanged",
			"expected": {"a": 1},
			"value": {"a": 1},
		},
		{
			"description": "a falsy non-dict value returns an empty dict",
			"expected": {},
			"value": "",
		},
	],
)
def test_to_python(payload):
	"""Test to_python passes dicts through and normalises falsy values to an empty dict"""

	with step(f"Arrange: {payload['description']}."):
		field = EncryptedJSONField()

	with step("Act: Call to_python."):
		result = field.to_python(payload["value"])

	with step("Assert: Result matches expected."):
		assert result == payload["expected"]


def test_to_python_decrypts_an_encrypted_token():
	"""Test to_python decrypts and deserialises an already-encrypted token"""

	with step("Arrange: An encrypted token for a real payload."):
		field = EncryptedJSONField()
		token = field.get_prep_value({"auth_driver": "b1s"})

	with step("Act: Call to_python on the token."):
		result = field.to_python(token)

	with step("Assert: The original payload is returned."):
		assert result == {"auth_driver": "b1s"}


def test_to_python_invalid_token_returns_empty_dict():
	"""Test to_python swallows decrypt/parse errors and returns an empty dict"""

	with step("Arrange: A value that is not a valid Fernet token."):
		field = EncryptedJSONField()

	with step("Act: Call to_python with garbage."):
		result = field.to_python("not-a-valid-token")

	with step("Assert: An empty dict is returned."):
		assert result == {}


def test_round_trip_through_a_real_save_and_reload():
	"""Test the field round-trips a dict through an actual DB save/reload via MOrganization.integration"""

	with step("Arrange: An org with a non-trivial integration payload."):
		org = FOrganization.create(
			integration={"auth_driver": "open_id", "client_secret": "s3cr3t"}
		)

	with step("Act: Reload the org from the database."):
		reloaded = MOrganization.objects.get(pk=org.pk)

	with step("Assert: The integration dict survives the round trip."):
		assert reloaded.integration == {
			"auth_driver": "open_id",
			"client_secret": "s3cr3t",
		}
