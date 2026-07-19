"""Encrypted model fields"""

# General imports
import json

# Lib imports
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


class EncryptedJSONField(models.TextField):
	"""Custom TextField that transparently encrypts a dict to/from the database."""

	# Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256). The raw DB
	# column stores the Fernet token (URL-safe base64 string); Python always
	# sees a plain dict — encryption/decryption is invisible to model code and
	# serializers. Requires FIELD_ENCRYPTION_KEY in Django settings — a
	# URL-safe base64 encoded 32-byte key generated with Fernet.generate_key().decode()

	description = "An encrypted JSON field"

	def _cipher(self):
		"""Return a Fernet instance keyed from settings."""
		return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())

	def deconstruct(self):
		"""Return enough information to recreate the field."""
		name, path, args, kwargs = super().deconstruct()  # pylint: disable=no-member
		return name, path, args, kwargs

	# pylint: disable=unused-argument
	def from_db_value(self, value, expression, connection):
		"""Decrypt and deserialise when reading from the database."""
		if not value:
			return {}
		try:
			decrypted = self._cipher().decrypt(value.encode()).decode()
			return json.loads(decrypted)
		except Exception:  # pylint: disable=broad-except
			return {}

	def get_prep_value(self, value):
		"""Serialise and encrypt before writing to the database."""
		if value is None:
			value = {}
		encrypted = self._cipher().encrypt(json.dumps(value).encode()).decode()
		return encrypted

	def to_python(self, value):
		"""Return a plain dict regardless of whether value is already decoded."""
		if isinstance(value, dict):
			return value
		if not value:
			return {}
		try:
			decrypted = self._cipher().decrypt(value.encode()).decode()
			return json.loads(decrypted)
		except Exception:  # pylint: disable=broad-except
			return {}
