"""Configuration for app test"""

# Lib imports
import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

# App imports
from core.tests.factories import FUser
from drf_api.tests.factories import (
	FBucketFile,
	FChatMessage,
	FChatSession,
	FOrganization,
	FSeat,
	FSession,
	FSessionProxy,
	FUsageEvent,
)

register(FBucketFile)
register(FChatMessage)
register(FChatSession)
register(FOrganization)
register(FSeat)
register(FSession)
register(FSessionProxy)
register(FUsageEvent)
register(FUser)


@pytest.fixture(scope="session")
def api_client():
	"""Return the DRF APIClient class."""
	return APIClient
