"""Base serializer"""

# General imports
from rest_framework import serializers


class BaseSerializer(serializers.HyperlinkedModelSerializer):
	"""Base serializer"""

	error_messages = {
		"blank": "CANNOT_BE_EMPTY",
		"null": "CANNOT_BE_EMPTY",
		"required": "CANNOT_BE_EMPTY",
	}

	class Meta:
		abstract = True


# pylint: disable-next=abstract-method
class BaseStrictSerializer(serializers.Serializer):
	"""Base for validation-only (non-model) payload contracts: rejects any field the caller
	sends that isn't declared, instead of silently dropping it. An undeclared field means
	the sender needs fixing, not filtering -- this makes that failure loud instead of hidden.
	Validation-only (never saved), so create/update are deliberately left unimplemented."""

	def to_internal_value(self, data):
		"""Reject any key not declared as a field before running normal field validation."""
		if hasattr(data, "keys"):
			unexpected = set(data.keys()) - set(self.fields)
			if unexpected:
				raise serializers.ValidationError(
					{key: "UNEXPECTED_FIELD" for key in unexpected}
				)
		return super().to_internal_value(data)
