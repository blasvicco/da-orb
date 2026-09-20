"""This module contains tests for BaseViewSet's soft-delete-aware get_queryset"""

# Lib imports
import pytest
from allure import step

# App imports
from drf_api.models import MChatSession, MOrganization
from drf_api.resources.base_viewset import BaseViewSet

pytestmark = pytest.mark.django_db


def test_get_queryset_excludes_soft_deleted_rows_when_model_has_deleted_on(
	f_chat_session,
):
	"""Test get_queryset filters out soft-deleted rows for a model declaring deleted_on"""

	with step(
		"Arrange: An active and a soft-deleted MChatSession, and a view bound to it."
	):
		active = f_chat_session.create()
		deleted = f_chat_session.create()
		deleted.delete()
		view = BaseViewSet()
		view.queryset = MChatSession.objects.all()

	with step("Act: Call get_queryset."):
		result = list(view.get_queryset())

	with step("Assert: Only the active session is returned."):
		assert result == [active]


def test_get_queryset_is_unfiltered_when_model_has_no_deleted_on(f_organization):
	"""Test get_queryset applies no soft-delete filter for a model without deleted_on"""

	with step("Arrange: Two organizations, and a view bound to MOrganization."):
		first = f_organization.create()
		second = f_organization.create()
		view = BaseViewSet()
		view.queryset = MOrganization.objects.all()

	with step("Act: Call get_queryset."):
		result = list(view.get_queryset())

	with step("Assert: Both organizations are returned."):
		assert set(result) == {first, second}
