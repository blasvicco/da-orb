"""This module contains tests for the organization-slug resolution middleware"""

# General imports
from unittest.mock import MagicMock

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.middleware.organization import MOrganizationMiddleware


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "plain host resolves the first label as the slug",
			"expected_slug": "acme",
			"host": "acme.orb.test",
		},
		{
			"description": "a port suffix is stripped before resolving the slug",
			"expected_slug": "acme",
			"host": "acme.orb.test:8000",
		},
		{
			"description": "a bare host with no dot resolves itself as the slug",
			"expected_slug": "localhost",
			"host": "localhost",
		},
	],
)
def test_call_resolves_org_slug(payload):
	"""Test MOrganizationMiddleware injects get_org_slug resolving the Host header's first label"""

	with step(f"Arrange: {payload['description']}."):
		request = MagicMock(get_host=MagicMock(return_value=payload["host"]))
		get_response = MagicMock(return_value="response")
		middleware = MOrganizationMiddleware(get_response)

	with step("Act: Call the middleware."):
		response = middleware(request)

	with step(
		"Assert: get_org_slug resolves correctly and the response is passed through."
	):
		assert request.get_org_slug() == payload["expected_slug"]
		get_response.assert_called_once_with(request)
		assert response == "response"


def test_call_swallows_host_resolution_errors():
	"""Test MOrganizationMiddleware falls back to a None slug when get_host raises"""

	with step("Arrange: A request whose get_host() raises."):
		request = MagicMock(get_host=MagicMock(side_effect=ValueError("boom")))
		get_response = MagicMock(return_value="response")
		middleware = MOrganizationMiddleware(get_response)

	with step("Act: Call the middleware."):
		middleware(request)

	with step("Assert: get_org_slug resolves to None."):
		assert request.get_org_slug() is None
