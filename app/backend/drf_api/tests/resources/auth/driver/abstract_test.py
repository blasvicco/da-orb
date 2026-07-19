"""This module contains tests for AAuthDriver's default (non-abstract) hooks"""

# Lib imports
from allure import step

# App imports
from drf_api.resources.auth.driver.abstract import AAuthDriver, AuthDriverError


class _StubDriver(AAuthDriver):
	"""Minimal concrete driver exposing only the abstract contract, for exercising AAuthDriver's default hooks."""

	def authenticate(self, **credentials) -> dict:
		"""Return a session dict from the given username, or raise if the token signals a failure."""
		if credentials.get("token") == "boom":
			raise AuthDriverError("AUTH_FAILED")
		return {"user": {"username": credentials.get("username", "")}}

	def login(self, request, org: str):
		"""Unused by these tests."""

	def refresh(self, **token_data) -> dict:
		"""Unused by these tests."""


def _make_driver():
	"""Build a stub driver instance with an empty integration config"""
	return _StubDriver({})


def test_resolve_ws_session_default_delegates_to_authenticate():
	"""Test the default resolve_ws_session forwards reconnect fields to authenticate()"""

	with step("Arrange: A stub driver and reconnect session data."):
		driver = _make_driver()

	with step("Act: Call resolve_ws_session."):
		result = driver.resolve_ws_session(
			{"database": "TESTDB", "expires_at": 123, "password": ""},
			org="acme",
			token="live-token",
			username="bob",
		)

	with step("Assert: The session dict built by authenticate() is returned."):
		assert result == {"user": {"username": "bob"}}


def test_resolve_ws_session_default_swallows_authenticate_failure():
	"""Test the default resolve_ws_session returns None when authenticate() raises"""

	with step("Arrange: A stub driver whose authenticate() fails for this token."):
		driver = _make_driver()

	with step("Act: Call resolve_ws_session with a token that triggers a failure."):
		result = driver.resolve_ws_session(
			{"database": "", "expires_at": 0, "password": ""},
			org="acme",
			token="boom",
			username="bob",
		)

	with step("Assert: None is returned."):
		assert result is None
