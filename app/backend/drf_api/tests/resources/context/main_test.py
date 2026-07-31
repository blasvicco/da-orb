"""This module contains tests for the context viewset"""

# Lib imports
import pytest
from allure import step
from rest_framework.test import APIRequestFactory

# App imports
from drf_api.resources.context.main import VSContext
from drf_api.tests.factories import FOrganization

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _make_request(org_slug):
	"""Build a DRF-compatible GET request scoped to the given org slug"""
	request = _factory.get("/")
	request.get_org_slug = lambda: org_slug
	return request


def test_get_returns_not_found_when_slug_is_blank():
	"""Test get raises NOT_FOUND when the request carries no resolvable org slug"""

	with step("Arrange: A request whose org slug resolves to an empty string."):
		request = _make_request("")

	with step("Act: Call get."):
		response = VSContext.as_view({"get": "get"})(request)

	with step("Assert: 404 NOT_FOUND is returned."):
		assert response.status_code == 404


def test_get_returns_not_found_when_org_does_not_exist():
	"""Test get raises NOT_FOUND when the org slug does not resolve to a real org"""

	with step("Arrange: A request against a slug with no matching org."):
		request = _make_request("does-not-exist")

	with step("Act: Call get."):
		response = VSContext.as_view({"get": "get"})(request)

	with step("Assert: 404 NOT_FOUND is returned."):
		assert response.status_code == 404


def test_get_returns_serialized_context():
	"""Test get returns the serialized public context for a resolvable org"""

	with step("Arrange: A persisted org."):
		org = FOrganization.create(
			integration={
				"auth_driver": "open_id",
				"base_url": "https://sap.example.com",
			}
		)
		request = _make_request(org.slug)

	with step("Act: Call get."):
		response = VSContext.as_view({"get": "get"})(request)

	with step("Assert: 200 with the serialized context."):
		assert response.status_code == 200
		assert response.data["auth_driver"] == "open_id"
		assert response.data["base_url"] == "https://sap.example.com"
