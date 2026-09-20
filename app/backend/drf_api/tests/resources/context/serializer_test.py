"""This module contains tests for the context serializer"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.resources.context.serializer import SContext
from drf_api.tests.factories import FOrganization

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "an open_id org exposes its auth_driver, base_url, and client_id",
			"expected": {
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "public-id",
			},
			"integration": {
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
				"client_id": "public-id",
				"client_secret": "super-secret",
			},
		},
		{
			"description": "a b1s org exposes its auth_driver/base_url but never a client_id",
			"expected": {
				"auth_driver": "b1s",
				"base_url": "https://b1s.example.com",
				"client_id": "",
			},
			"integration": {
				"auth_driver": "b1s",
				"base_url": "https://b1s.example.com",
			},
		},
		{
			"description": "an org with no integration config defaults to open_id with blank fields",
			"expected": {"auth_driver": "open_id", "base_url": "", "client_id": ""},
			"integration": {},
		},
	],
)
def test_serializes_public_fields_only(payload):
	"""Test SContext exposes only auth_driver/base_url/client_id, never client_secret"""

	with step(f"Arrange: {payload['description']}."):
		org = FOrganization.create(integration=payload["integration"])

	with step("Act: Serialize the org."):
		data = SContext(org).data

	with step("Assert: Only the expected public fields are present."):
		assert dict(data) == payload["expected"]
