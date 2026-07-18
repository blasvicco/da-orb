"""This module contains tests for core views"""

# Lib imports
import pytest
from allure import step
from django.test import RequestFactory

# App imports
from core.views import healthcheck

pytestmark = pytest.mark.django_db


def test_healthcheck():
	"""Test healthcheck view returns pong with correct content type"""

	with step("Arrange: Create a GET request."):
		request = RequestFactory().get("/healthcheck")

	with step("Act: Call healthcheck view."):
		response = healthcheck(request)

	with step("Assert: Response is 200 with correct body and content type."):
		assert response.status_code == 200
		assert response.content == b"pong"
		assert "text/plain" in response["Content-Type"]
