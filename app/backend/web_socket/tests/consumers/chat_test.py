"""This module contains tests for the chat WebSocket consumer connection_key scoping"""

# General imports
from unittest.mock import AsyncMock, MagicMock, patch

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync

# App imports
from drf_api.models import MChatSession, MOrganization
from web_socket.consumers.chat import CChat, _create_session, _load_session

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def _make_consumer(resume_session_id=None, session=None):
	"""Build a CChat instance with a mocked scope/user and no live Redis dependency"""
	consumer = CChat()
	consumer.scope = {"organization": _make_org()}
	consumer.user = MagicMock(session=session, username="bob")
	consumer._resume_session_id = resume_session_id  # pylint: disable=protected-access
	return consumer


@pytest.mark.django_db(transaction=True)
def test_create_session_persists_connection_key():
	"""Test _create_session stores the connection_key on the new MChatSession row"""

	with step("Arrange: An organization to attach the session to."):
		org = _make_org()

	with step("Act: Call _create_session."):
		session = async_to_sync(_create_session)(
			connection_key="TESTDB", language="es", org=org, username="bob"
		)

	with step("Assert: The row was persisted with the connection_key."):
		assert session.connection_key == "TESTDB"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "matching connection_key returns the session",
			"found": True,
			"lookup_connection_key": "TESTDB",
			"row_connection_key": "TESTDB",
		},
		{
			"description": "mismatched connection_key returns None",
			"found": False,
			"lookup_connection_key": "OTHERDB",
			"row_connection_key": "TESTDB",
		},
	],
)
def test_load_session_scoped_by_connection_key(payload):
	"""Test _load_session only returns a row when the connection_key matches"""

	with step(f"Arrange: {payload['description']}."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key=payload["row_connection_key"], org=org, username="bob"
		)

	with step("Act: Call _load_session."):
		result = async_to_sync(_load_session)(
			connection_key=payload["lookup_connection_key"],
			org_id=org.id,
			session_id=session.id,
			username="bob",
		)

	with step("Assert: Result matches expectation."):
		if payload["found"]:
			assert result.id == session.id
		else:
			assert result is None


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "session carries a connection_key",
			"expected": "TESTDB",
			"session": MagicMock(connection_key="TESTDB"),
		},
		{
			"description": "user has no session",
			"expected": "",
			"session": None,
		},
	],
)
def test_resolve_context_computes_connection_key(payload):
	"""Test resolve_context derives connection_key from the authenticated session"""

	with step(f"Arrange: {payload['description']}."):
		consumer = _make_consumer(session=payload["session"])

	with step("Act: Call resolve_context with the n8n Redis helpers mocked out."):
		with patch("web_socket.consumers.chat.N8nClient"), patch(
			"web_socket.consumers.chat.N8nQueueState"
		), patch("web_socket.consumers.chat.N8nSessionState") as mock_state:
			mock_state.return_value.clear = AsyncMock()
			async_to_sync(consumer.resolve_context)()

	with step("Assert: connection_key matches expectation."):
		assert consumer.connection_key == payload["expected"]
