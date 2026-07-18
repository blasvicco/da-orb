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
