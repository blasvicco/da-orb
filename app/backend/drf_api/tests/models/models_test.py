"""This module contains tests for drf_api models __str__ methods"""

# Lib imports
import pytest
from allure import step

# App imports
# from drf_api.models import MOrganization

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
	"fixture_name",
	[
		"f_organization",
	],
)
def test_model_str(fixture_name, request):
	"""Test __str__ returns a non-empty string for all models"""

	with step(f"Arrange/Act: Create {fixture_name} instance."):
		factory = request.getfixturevalue(fixture_name)
		instance = factory.create()

	with step("Assert: __str__ returns a non-empty string."):
		assert isinstance(str(instance), str)
		assert len(str(instance)) > 0
