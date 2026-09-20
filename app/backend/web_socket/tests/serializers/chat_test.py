"""This module contains tests for the chat WebSocket payload-curation serializers"""

# Lib imports
import pytest
from allure import step

# App imports
from web_socket.serializers import SActiveNodeSwitch, SMessageSend


@pytest.mark.parametrize(
	"payload",
	[
		{
			"data": {"message": "hi"},
			"description": "language is missing entirely",
			"valid": False,
		},
		{
			"data": {"language": "", "message": "hi"},
			"description": "language is blank",
			"valid": False,
		},
		{
			"data": {"expertise_level": 2, "language": "es"},
			"description": "message may be absent/blank",
			"valid": True,
		},
	],
)
def test_message_send_language_must_never_be_empty(payload):
	"""Test SMessageSend rejects a payload with no language, or a blank one -- language must never be empty"""

	with step(f"Arrange: {payload['description']}."):
		serializer = SMessageSend(data=payload["data"])

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validity matches expectation."):
		assert valid is payload["valid"]


@pytest.mark.parametrize(
	"payload",
	[
		{
			"data": {"language": "es"},
			"description": "expertise_level is missing entirely",
			"valid": False,
		},
		{
			"data": {"expertise_level": 0, "language": "es"},
			"description": "expertise_level is below the valid range",
			"valid": False,
		},
		{
			"data": {"expertise_level": 4, "language": "es"},
			"description": "expertise_level is above the valid range",
			"valid": False,
		},
		{
			"data": {"expertise_level": 2, "language": "es"},
			"description": "expertise_level is a valid value",
			"valid": True,
		},
	],
)
def test_message_send_expertise_level_must_always_be_present_and_in_range(payload):
	"""Test SMessageSend rejects a payload with no expertise_level, or one out of the 1-3
	range -- same as language, there is no fallback here, the frontend must always send it"""

	with step(f"Arrange: {payload['description']}."):
		serializer = SMessageSend(data=payload["data"])

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validity matches expectation."):
		assert valid is payload["valid"]


def test_message_send_rejects_an_undeclared_field():
	"""Test SMessageSend rejects a payload carrying a field it doesn't declare -- an undeclared
	field means the frontend needs fixing, not something for this serializer to silently drop"""

	with step(
		"Arrange: A payload carrying an undeclared field alongside the real ones."
	):
		serializer = SMessageSend(
			data={"language": "es", "message": "hi", "some_other_field": "junk"}
		)

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validation fails, naming the undeclared field."):
		assert not valid
		assert "some_other_field" in serializer.errors


def test_message_send_applies_defaults_for_the_declared_fields():
	"""Test SMessageSend's validated_data carries the right defaults for optional fields"""

	with step("Arrange: A payload with only the required fields."):
		serializer = SMessageSend(data={"expertise_level": 2, "language": "es"})

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step(
		"Assert: validated_data is exactly the declared field set, defaults applied."
	):
		assert valid
		assert set(serializer.validated_data.keys()) == {
			"bucket_file_ids",
			"expertise_level",
			"language",
			"message",
		}
		assert serializer.validated_data["bucket_file_ids"] == []


def test_active_node_switch_defaults_to_none_when_absent():
	"""Test SActiveNodeSwitch defaults active_node_id to None rather than requiring it"""

	with step("Arrange: An empty payload."):
		serializer = SActiveNodeSwitch(data={})

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validation succeeds with active_node_id defaulted to None."):
		assert valid
		assert serializer.validated_data["active_node_id"] is None


def test_active_node_switch_rejects_a_non_string_id():
	"""Test SActiveNodeSwitch rejects an active_node_id that isn't a string"""

	with step("Arrange: A payload with a list instead of a string id."):
		serializer = SActiveNodeSwitch(data={"active_node_id": ["not", "a", "string"]})

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validation fails."):
		assert not valid


def test_active_node_switch_text_defaults_to_blank_when_absent():
	"""Test SActiveNodeSwitch defaults text to "" rather than requiring it -- a caller
	that only wants the Redis-state move, with no announcement bubble, may omit it"""

	with step("Arrange: A payload with no text field."):
		serializer = SActiveNodeSwitch(data={"active_node_id": "n2#0"})

	with step("Act: Call is_valid."):
		valid = serializer.is_valid()

	with step("Assert: Validation succeeds with text defaulted to blank."):
		assert valid
		assert serializer.validated_data["text"] == ""
