"""This module contains tests for the MOrganization model"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MOrganization

pytestmark = pytest.mark.django_db


def test_safe_to_dict_strips_client_secret():
	"""Test safe_to_dict removes client_secret from integration but keeps other keys"""

	with step("Arrange: An org with a full open_id integration config."):
		org = MOrganization.objects.create(
			integration={
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "public-id",
				"client_secret": "super-secret",
			},
			name="acme",
			slug="acme",
		)

	with step("Act: Call safe_to_dict."):
		data = org.safe_to_dict()

	with step("Assert: client_secret is gone, everything else survives."):
		assert "client_secret" not in data["integration"]
		assert data["integration"]["auth_driver"] == "open_id"
		assert data["integration"]["base_url"] == "https://sap.example.com"
		assert data["integration"]["client_id"] == "public-id"


def test_safe_to_dict_b1s_has_no_secret_to_strip():
	"""Test safe_to_dict is a no-op on integration keys for a b1s org (no client_secret present)"""

	with step("Arrange: A b1s org with no client_secret in its integration config."):
		org = MOrganization.objects.create(
			integration={"auth_driver": "b1s", "base_url": "https://b1s.example.com"},
			name="acme",
			slug="acme",
		)

	with step("Act: Call safe_to_dict."):
		data = org.safe_to_dict()

	with step("Assert: integration is returned unchanged."):
		assert data["integration"] == org.integration
