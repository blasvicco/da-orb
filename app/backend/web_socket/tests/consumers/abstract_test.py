"""This module contains tests for the abstract WebSocket consumer"""

# General imports
from unittest.mock import AsyncMock, MagicMock

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync

# App imports
from web_socket.consumers.abstract import CAbstract, ConsumerGroupError

pytestmark = pytest.mark.django_db


def _make_consumer(group_name="test_group"):
	"""Build a CAbstract instance with mocked async internals"""
	consumer = CAbstract()
	consumer.group_name = group_name
	consumer.channel_name = "test_channel"
	consumer.channel_layer = MagicMock()
	consumer.channel_layer.group_add = AsyncMock()
	consumer.channel_layer.group_discard = AsyncMock()
	consumer.send_json = AsyncMock()
	consumer.close = AsyncMock()
	consumer.accept = AsyncMock()
	return consumer


@pytest.mark.parametrize(
	"payload",
	[
		{
			"auth_driver": "b1s",
			"description": "B1S org: middleware-resolved session is not overwritten by client fields",
			"expect_patched": False,
		},
		{
			"auth_driver": "open_id",
			"description": "Open ID org: client-supplied fields still patch the session",
			"expect_patched": True,
		},
		{
			"auth_driver": None,
			"description": "No organization in scope: client-supplied fields still patch the session",
			"expect_patched": True,
		},
	],
)
def test_auth_init(payload):
	"""Test auth_init only patches password/database from client fields for non-B1S orgs"""

	with step(f"Arrange: {payload['description']}"):
		consumer = _make_consumer()
		consumer.get_group_name = MagicMock(return_value="test_group")
		organization = None
		if payload["auth_driver"] is not None:
			organization = MagicMock(
				integration={"auth_driver": payload["auth_driver"]}
			)
		consumer.scope = {"organization": organization}
		consumer.user = MagicMock()
		consumer.user.session = MagicMock(
			database="MIDDLEWAREDB",
			user={"password": "middleware-password", "username": "bob"},
		)

	with step("Act: Call auth_init with different client-supplied credentials."):
		async_to_sync(consumer.auth_init)(
			{"database": "CLIENTDB", "password": "client-password"}
		)

	with step("Assert: Patch behaviour matches expectation."):
		if payload["expect_patched"]:
			assert consumer.user.session.user["password"] == "client-password"
			assert consumer.user.session.database == "CLIENTDB"
		else:
			assert consumer.user.session.user["password"] == "middleware-password"
			assert consumer.user.session.database == "MIDDLEWAREDB"
		consumer.send_json.assert_awaited_once()


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "unauthenticated user is closed immediately",
			"expect_accept": False,
			"expect_close": True,
			"is_authenticated": False,
		},
		{
			"description": "authenticated user is accepted but not yet added to its group",
			"expect_accept": True,
			"expect_close": False,
			"is_authenticated": True,
		},
	],
)
def test_connect(payload):
	"""Test connect closes unauthenticated users and accepts authenticated ones without joining the group."""
	# Joining the channel group happens in auth_init, once credentials are verified.

	with step(f"Arrange: {payload['description']}"):
		consumer = _make_consumer()
		mock_user = MagicMock()
		mock_user.is_authenticated = payload["is_authenticated"]
		consumer.scope = {"user": mock_user}

	with step("Act: Call connect."):
		async_to_sync(consumer.connect)()

	with step("Assert: Correct flow was followed."):
		if payload["expect_close"]:
			consumer.close.assert_awaited_once()
			consumer.accept.assert_not_awaited()
		else:
			consumer.close.assert_not_awaited()
			consumer.accept.assert_awaited_once()
		consumer.channel_layer.group_add.assert_not_awaited()


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "with group_name calls group_discard",
			"expect_discard": True,
			"group_name": "test_group",
		},
		{
			"description": "without group_name skips group_discard",
			"expect_discard": False,
			"group_name": None,
		},
	],
)
def test_disconnect(payload):
	"""Test disconnect discards channel from group only when group_name is set"""

	with step(f"Arrange: {payload['description']}"):
		consumer = _make_consumer(group_name=payload["group_name"])

	with step("Act: Call disconnect."):
		async_to_sync(consumer.disconnect)(1001)

	with step("Assert: group_discard called only when group_name is set."):
		if payload["expect_discard"]:
			consumer.channel_layer.group_discard.assert_awaited_once()
		else:
			consumer.channel_layer.group_discard.assert_not_awaited()


@pytest.mark.parametrize(
	"payload",
	[
		{
			"assert_handler": False,
			"assert_raises": None,
			"assert_send_json": True,
			"auth_ready": False,
			"description": "broadcast sends payload via send_json",
			"input": {"payload": {"type": "test.event"}},
			"method": "broadcast",
			"setup_handler": None,
		},
		{
			"assert_handler": False,
			"assert_raises": ConsumerGroupError,
			"assert_send_json": False,
			"auth_ready": False,
			"description": "get_group_name raises ConsumerGroupError",
			"input": None,
			"method": "get_group_name",
			"setup_handler": None,
		},
		{
			"assert_handler": True,
			"assert_raises": None,
			"assert_send_json": False,
			"auth_ready": True,
			"description": "receive_json dispatches known type to method once auth is ready",
			"input": {"type": "log.event"},
			"method": "receive_json",
			"setup_handler": "log_event",
		},
		{
			"assert_handler": False,
			"assert_raises": None,
			"assert_send_json": False,
			"auth_ready": True,
			"description": "receive_json silently ignores unknown type once auth is ready",
			"input": {"type": "no.such.thing"},
			"method": "receive_json",
			"setup_handler": None,
		},
		{
			"assert_handler": False,
			"assert_raises": None,
			"assert_send_json": False,
			"auth_ready": False,
			"description": "receive_json blocks any type except auth_init before auth is ready",
			"input": {"type": "log.event"},
			"method": "receive_json",
			"setup_handler": "log_event",
		},
	],
)
def test_consumer_interface(payload):
	"""Test broadcast, get_group_name, and receive_json dispatch behaviour"""

	with step(f"Arrange: {payload['description']}"):
		consumer = _make_consumer()
		consumer._auth_ready = payload["auth_ready"]  # pylint: disable=protected-access
		mock_handler = None
		if payload["setup_handler"]:
			mock_handler = AsyncMock(return_value=None)
			setattr(consumer, payload["setup_handler"], mock_handler)

	with step("Act: Call the target method."):
		if payload["assert_raises"]:
			with pytest.raises(payload["assert_raises"]):
				getattr(consumer, payload["method"])()
			return

		if payload["method"] == "broadcast":
			async_to_sync(consumer.broadcast)(payload["input"])
			result = None
		else:
			result = async_to_sync(consumer.receive_json)(payload["input"])

	with step("Assert: Expected side effects occurred."):
		if payload["assert_send_json"]:
			consumer.send_json.assert_awaited_once_with(payload["input"]["payload"])
		if payload["assert_handler"] and mock_handler:
			mock_handler.assert_awaited_once_with(payload["input"])
		if not payload["assert_handler"] and not payload["assert_send_json"]:
			assert result is None
			if mock_handler:
				mock_handler.assert_not_awaited()


def test_resolve_context_base_returns_none():
	"""Test base resolve_context is a no-op returning None"""

	with step("Arrange/Act: Call base resolve_context directly."):
		result = async_to_sync(_make_consumer().resolve_context)()

	with step("Assert: Returns None."):
		assert result is None
