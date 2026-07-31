"""This module contains tests for the chat WebSocket consumer connection_key scoping"""

# General imports
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Lib imports
import pytest
from allure import step
from asgiref.sync import async_to_sync
from django.db import IntegrityError

# App imports
from drf_api.models import MChatMessage, MChatSession, MOrganization
from web_socket.consumers.abstract import CAbstract
from web_socket.consumers.chat import (
	_MSG_AGENT_ERROR,
	_MSG_AGENT_UNAVAILABLE,
	_MSG_QUEUED,
	CChat,
	_create_session,
	_load_session,
	_save_message,
	_set_session_title,
)
from web_socket.helpers.n8n import N8nClientError

pytestmark = pytest.mark.django_db


def _make_org(slug="acme"):
	"""Create a persisted MOrganization instance"""
	return MOrganization.objects.create(name=slug, slug=slug)


def _make_consumer(resume_session_id=None, session=None):
	"""Build a CChat instance with a mocked scope/user/channel layer and no live Redis dependency"""
	org = _make_org()
	consumer = CChat()
	consumer.scope = {"organization": org}
	consumer.organization = org
	consumer.user = MagicMock(session=session, username="bob")
	consumer.channel_layer = MagicMock(group_send=AsyncMock())
	consumer.send_json = AsyncMock()
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


# ---------------------------------------------------------------------------
# DB helpers: _save_message / _set_session_title
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_save_message_persists_row():
	"""Test _save_message stores a message row against the given session"""

	with step("Arrange: A persisted session."):
		org = _make_org()
		session = MChatSession.objects.create(org=org, username="bob")

	with step("Act: Call _save_message."):
		async_to_sync(_save_message)(
			session, "user", "hello", None, "2025-01-01T00:00:00+00:00"
		)

	with step("Assert: The message row was persisted."):
		message = MChatMessage.objects.get(session=session)
		assert message.text == "hello"
		assert message.type == "user"


@pytest.mark.django_db(transaction=True)
def test_set_session_title_updates_db_and_instance():
	"""Test _set_session_title updates both the DB row and the in-memory instance"""

	with step("Arrange: A persisted session with a blank title."):
		org = _make_org()
		session = MChatSession.objects.create(org=org, title="", username="bob")

	with step("Act: Call _set_session_title."):
		async_to_sync(_set_session_title)(session, "New title")

	with step("Assert: Both the DB row and the instance carry the new title."):
		assert session.title == "New title"
		session.refresh_from_db()
		assert session.title == "New title"


# ---------------------------------------------------------------------------
# get_group_name / _get_auth_ok_extra
# ---------------------------------------------------------------------------


def test_get_group_name_uses_resume_session_id_when_present():
	"""Test get_group_name keys the group on the resumed session id"""

	with step("Arrange: A consumer resuming an existing chat."):
		consumer = _make_consumer(resume_session_id=42)

	with step("Act: Call get_group_name."):
		name = consumer.get_group_name()

	with step("Assert: The group name is keyed on the resumed session id."):
		assert name == f"chat_{consumer.organization.id}_bob_42"


def test_get_group_name_generates_a_stable_token_for_a_new_chat():
	"""Test get_group_name generates a per-connection token that stays stable across calls"""

	with step("Arrange: A consumer with no resumed session."):
		consumer = _make_consumer()

	with step("Act: Call get_group_name twice."):
		first = consumer.get_group_name()
		second = consumer.get_group_name()

	with step("Assert: Both calls return the same, freshly generated token."):
		assert first == second
		assert consumer._new_chat_token in first  # pylint: disable=protected-access


@pytest.mark.parametrize(
	"payload",
	[
		{"chat_session": None, "description": "no chat_session yet", "expected": {}},
		{
			"chat_session": SimpleNamespace(id=7),
			"description": "chat_session present",
			"expected": {"session_id": 7},
		},
	],
)
def test_get_auth_ok_extra(payload):
	"""Test _get_auth_ok_extra includes session_id only once a chat_session exists"""

	with step(f"Arrange: {payload['description']}."):
		consumer = _make_consumer()
		consumer.chat_session = payload["chat_session"]

	with step("Act: Call _get_auth_ok_extra."):
		result = consumer._get_auth_ok_extra()  # pylint: disable=protected-access

	with step("Assert: Result matches expected."):
		assert result == payload["expected"]


def test_auth_init_captures_resume_session_id_before_delegating(mocker):
	"""Test CChat.auth_init captures session_id then delegates to the parent implementation"""

	with step("Arrange: A consumer and a mocked parent auth_init."):
		consumer = _make_consumer()
		mock_super_auth_init = mocker.patch.object(CAbstract, "auth_init", AsyncMock())

	with step("Act: Call auth_init with a session_id."):
		async_to_sync(consumer.auth_init)({"session_id": 99})

	with step("Assert: The resume id was captured and the parent was awaited."):
		assert consumer._resume_session_id == 99  # pylint: disable=protected-access
		mock_super_auth_init.assert_awaited_once_with({"session_id": 99})


# ---------------------------------------------------------------------------
# _resolve_process_selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	"payload",
	[
		{
			"description": "no pending processes returns the text unchanged",
			"expected": "hello",
			"pending": None,
			"text": "hello",
		},
		{
			"description": "numeric selection resolves to the matching process",
			"expected": "approve_po",
			"pending": [{"name": "create_po"}, {"name": "approve_po"}],
			"text": "2",
		},
		{
			"description": "out-of-range numeric selection falls back to the raw text",
			"expected": "9",
			"pending": [{"name": "create_po"}],
			"text": "9",
		},
		{
			"description": "letter selection resolves to the matching process",
			"expected": "approve_po",
			"pending": [{"name": "create_po"}, {"name": "approve_po"}],
			"text": "b",
		},
		{
			"description": "out-of-range letter selection falls back to the raw text",
			"expected": "z",
			"pending": [{"name": "create_po"}],
			"text": "z",
		},
		{
			"description": "free-form text with pending processes falls back to the raw text",
			"expected": "hello",
			"pending": [{"name": "create_po"}],
			"text": "hello",
		},
	],
)
def test_resolve_process_selection(payload):
	"""Test _resolve_process_selection maps numeric/letter replies to a pending process name"""

	with step(f"Arrange: {payload['description']}."):
		consumer = _make_consumer()
		consumer.pending_processes = payload["pending"]

	with step("Act: Call _resolve_process_selection."):
		result = (
			consumer._resolve_process_selection(  # pylint: disable=protected-access
				payload["text"]
			)
		)

	with step("Assert: Result matches expected and pending_processes is cleared."):
		assert result == payload["expected"]
		assert consumer.pending_processes is None


# ---------------------------------------------------------------------------
# _broadcast
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_broadcast_persists_message_for_non_ephemeral_types():
	"""Test _broadcast sends to the channel group and persists non-system/status messages"""

	with step("Arrange: A consumer with a persisted chat_session."):
		consumer = _make_consumer()
		consumer.chat_session = MChatSession.objects.create(
			org=consumer.organization, username="bob"
		)

	with step("Act: Call _broadcast with an 'agent' message."):
		async_to_sync(consumer._broadcast)(  # pylint: disable=protected-access
			"hello", "agent"
		)

	with step("Assert: The group was notified and the message was persisted."):
		consumer.channel_layer.group_send.assert_awaited_once()
		assert MChatMessage.objects.filter(session=consumer.chat_session).exists()


def test_broadcast_merges_extra_fields_into_the_payload():
	"""Test _broadcast merges the extra dict into the broadcast payload"""

	with step("Arrange: A consumer with no chat_session and an extra payload."):
		consumer = _make_consumer()
		consumer.chat_session = None

	with step("Act: Call _broadcast with an extra dict."):
		async_to_sync(consumer._broadcast)(  # pylint: disable=protected-access
			"status update", "status", extra={"processes": [{"name": "x"}]}
		)

	with step("Assert: The sent payload includes the merged extra field."):
		sent_event = consumer.channel_layer.group_send.call_args.args[1]
		assert sent_event["payload"]["processes"] == [{"name": "x"}]


@pytest.mark.parametrize("msg_type", ["system", "status"])
def test_broadcast_skips_persistence_for_ephemeral_types(mocker, msg_type):
	"""Test _broadcast never persists system/status messages"""

	with step(f"Arrange: A consumer with a chat_session and msg_type={msg_type}."):
		consumer = _make_consumer()
		consumer.chat_session = SimpleNamespace(pk=1)
		mock_save = mocker.patch("web_socket.consumers.chat._save_message", AsyncMock())

	with step("Act: Call _broadcast."):
		async_to_sync(consumer._broadcast)(  # pylint: disable=protected-access
			"queued", msg_type
		)

	with step("Assert: No message was persisted."):
		mock_save.assert_not_awaited()


def test_broadcast_skips_persistence_without_a_chat_session(mocker):
	"""Test _broadcast never persists when no chat_session exists yet"""

	with step("Arrange: A consumer with no chat_session."):
		consumer = _make_consumer()
		consumer.chat_session = None
		mock_save = mocker.patch("web_socket.consumers.chat._save_message", AsyncMock())

	with step("Act: Call _broadcast."):
		async_to_sync(consumer._broadcast)(  # pylint: disable=protected-access
			"hello", "agent"
		)

	with step("Assert: No message was persisted."):
		mock_save.assert_not_awaited()


def test_broadcast_clears_chat_session_on_integrity_error(mocker):
	"""Test _broadcast drops the chat_session reference if it was deleted before the save"""

	with step("Arrange: A consumer whose _save_message raises IntegrityError."):
		consumer = _make_consumer()
		consumer.chat_session = SimpleNamespace(pk=1)
		mocker.patch(
			"web_socket.consumers.chat._save_message",
			AsyncMock(side_effect=IntegrityError()),
		)

	with step("Act: Call _broadcast."):
		async_to_sync(consumer._broadcast)(  # pylint: disable=protected-access
			"hello", "agent"
		)

	with step("Assert: chat_session was cleared instead of raising."):
		assert consumer.chat_session is None


# ---------------------------------------------------------------------------
# message_send
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_message_send_creates_session_on_first_message(mocker):
	"""Test message_send lazily creates and titles the session on the first message"""

	with step("Arrange: A consumer with no chat_session yet."):
		consumer = _make_consumer()
		consumer.connection_key = "TESTDB"
		consumer.chat_session = None
		consumer.n8n_queue = MagicMock(try_start=AsyncMock(return_value=True))
		mock_fire = mocker.patch.object(consumer, "_fire_n8n", AsyncMock())
		mock_broadcast = mocker.patch.object(consumer, "_broadcast", AsyncMock())

	with step("Act: Call message_send with the first message."):
		async_to_sync(consumer.message_send)({"message": "Hello there"})

	with step("Assert: A session was created, titled, announced, and fired to n8n."):
		assert consumer.chat_session is not None
		assert consumer.chat_session.connection_key == "TESTDB"
		assert consumer.chat_session.title == "Hello there"
		consumer.send_json.assert_awaited_once_with(
			{"session_id": consumer.chat_session.id, "type": "session.created"}
		)
		mock_broadcast.assert_awaited_once_with("Hello there", "user")
		mock_fire.assert_called_once_with("Hello there", expertise_level=2)


@pytest.mark.django_db(transaction=True)
def test_message_send_uses_the_authenticated_session_language(mocker):
	"""Test message_send reads the new session's language from the authenticated session, when present"""

	with step(
		"Arrange: A consumer whose user carries an authenticated session with a language."
	):
		consumer = _make_consumer(session=SimpleNamespace(language="en"))
		consumer.connection_key = "TESTDB"
		consumer.chat_session = None
		consumer.n8n_queue = MagicMock(try_start=AsyncMock(return_value=True))
		mocker.patch.object(consumer, "_fire_n8n", AsyncMock())
		mocker.patch.object(consumer, "_broadcast", AsyncMock())

	with step("Act: Call message_send with the first message."):
		async_to_sync(consumer.message_send)({"message": "Hello there"})

	with step(
		"Assert: The new session was created with the authenticated session's language."
	):
		assert consumer.chat_session.language == "en"


@pytest.mark.django_db(transaction=True)
def test_message_send_retitles_session_after_process_selection(mocker):
	"""Test message_send retitles an existing session once a process selection is resolved"""

	with step("Arrange: An existing session and a pending process selection."):
		consumer = _make_consumer()
		consumer.connection_key = "TESTDB"
		consumer.chat_session = MChatSession.objects.create(
			connection_key="TESTDB",
			org=consumer.organization,
			title="old title",
			username="bob",
		)
		consumer.pending_processes = [{"name": "create_purchase_order"}]
		consumer.n8n_queue = MagicMock(try_start=AsyncMock(return_value=True))
		mocker.patch.object(consumer, "_fire_n8n", AsyncMock())
		mocker.patch.object(consumer, "_broadcast", AsyncMock())

	with step("Act: Call message_send with a resolvable selection."):
		async_to_sync(consumer.message_send)({"message": "1"})

	with step("Assert: The session title reflects the resolved process name."):
		consumer.chat_session.refresh_from_db()
		assert consumer.chat_session.title == "create_purchase_order"


@pytest.mark.django_db(transaction=True)
def test_message_send_queues_when_execution_already_in_flight(mocker):
	"""Test message_send queues the message and notifies the user when another execution is in flight"""

	with step("Arrange: An existing session and an in-flight n8n execution."):
		consumer = _make_consumer()
		consumer.connection_key = "TESTDB"
		consumer.chat_session = MChatSession.objects.create(
			connection_key="TESTDB", org=consumer.organization, username="bob"
		)
		consumer.n8n_queue = MagicMock(
			set_pending=AsyncMock(), try_start=AsyncMock(return_value=False)
		)
		consumer.user.to_dict = MagicMock(return_value={"username": "bob"})
		mocker.patch.object(
			consumer.organization, "safe_to_dict", return_value={"slug": "acme"}
		)
		mock_broadcast = mocker.patch.object(consumer, "_broadcast", AsyncMock())

	with step("Act: Call message_send."):
		async_to_sync(consumer.message_send)({"message": "hello"})

	with step("Assert: The message was queued and a status notice was broadcast."):
		consumer.n8n_queue.set_pending.assert_awaited_once()
		queued_payload = consumer.n8n_queue.set_pending.call_args.args[0]
		assert queued_payload["message"] == "hello"
		assert queued_payload["organization"] == {"slug": "acme"}
		mock_broadcast.assert_any_call(_MSG_QUEUED, "status")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
	"payload",
	[
		{"description": "a valid level is kept", "expected": 3, "given": 3},
		{"description": "an invalid level falls back to 2", "expected": 2, "given": 99},
	],
)
def test_message_send_normalises_expertise_level(mocker, payload):
	"""Test message_send only accepts expertise_level 1/2/3, defaulting anything else to 2"""

	with step(f"Arrange: {payload['description']}."):
		consumer = _make_consumer()
		consumer.connection_key = "TESTDB"
		consumer.chat_session = MChatSession.objects.create(
			connection_key="TESTDB", org=consumer.organization, username="bob"
		)
		consumer.n8n_queue = MagicMock(try_start=AsyncMock(return_value=True))
		mock_fire = mocker.patch.object(consumer, "_fire_n8n", AsyncMock())
		mocker.patch.object(consumer, "_broadcast", AsyncMock())

	with step("Act: Call message_send with the given expertise_level."):
		async_to_sync(consumer.message_send)(
			{"expertise_level": payload["given"], "message": "hi"}
		)

	with step("Assert: _fire_n8n was called with the normalised level."):
		mock_fire.assert_called_once_with("hi", expertise_level=payload["expected"])


# ---------------------------------------------------------------------------
# _fire_n8n
# ---------------------------------------------------------------------------


def test_fire_n8n_succeeds_on_first_attempt():
	"""Test _fire_n8n returns without broadcasting an error when the first attempt succeeds"""

	with step("Arrange: A consumer whose n8n_client.fire succeeds."):
		consumer = _make_consumer()
		consumer.chat_session = SimpleNamespace(id=1)
		consumer.n8n_client = MagicMock(fire=AsyncMock())
		consumer.n8n_state = MagicMock()

	with step("Act: Call _fire_n8n."):
		async_to_sync(consumer._fire_n8n)("hello")  # pylint: disable=protected-access

	with step("Assert: fire was called exactly once, no error broadcast."):
		consumer.n8n_client.fire.assert_awaited_once()


def test_fire_n8n_retries_then_gives_up_on_client_error(mocker):
	"""Test _fire_n8n retries on N8nClientError, then releases the lock and notifies once exhausted"""

	with step(
		"Arrange: A consumer whose n8n_client.fire always raises N8nClientError."
	):
		consumer = _make_consumer()
		consumer.chat_session = SimpleNamespace(id=1)
		consumer.n8n_client = MagicMock(
			fire=AsyncMock(side_effect=N8nClientError("boom"))
		)
		consumer.n8n_state = MagicMock()
		consumer.n8n_queue = MagicMock(release=AsyncMock())
		mock_broadcast = mocker.patch.object(consumer, "_broadcast", AsyncMock())
		mock_fire_pending = mocker.patch.object(
			consumer, "_fire_pending_if_any", AsyncMock()
		)
		mocker.patch("web_socket.consumers.chat.asyncio.sleep", AsyncMock())

	with step("Act: Call _fire_n8n with a small retry budget."):
		async_to_sync(consumer._fire_n8n)(  # pylint: disable=protected-access
			"hello", max_retries=2, retry_delay=0
		)

	with step(
		"Assert: Retried up to the limit, released the lock, and notified the user."
	):
		assert consumer.n8n_client.fire.await_count == 2
		consumer.n8n_queue.release.assert_awaited_once()
		mock_broadcast.assert_awaited_once_with(_MSG_AGENT_UNAVAILABLE, "alert")
		mock_fire_pending.assert_awaited_once()


def test_fire_n8n_handles_generic_exception_immediately(mocker):
	"""Test _fire_n8n does not retry on a non-N8nClientError, failing fast instead"""

	with step("Arrange: A consumer whose n8n_client.fire raises a generic exception."):
		consumer = _make_consumer()
		consumer.chat_session = SimpleNamespace(id=1)
		consumer.n8n_client = MagicMock(
			fire=AsyncMock(side_effect=RuntimeError("boom"))
		)
		consumer.n8n_state = MagicMock()
		consumer.n8n_queue = MagicMock(release=AsyncMock())
		mock_broadcast = mocker.patch.object(consumer, "_broadcast", AsyncMock())
		mock_fire_pending = mocker.patch.object(
			consumer, "_fire_pending_if_any", AsyncMock()
		)

	with step("Act: Call _fire_n8n."):
		async_to_sync(consumer._fire_n8n)("hello")  # pylint: disable=protected-access

	with step(
		"Assert: No retry happened, the lock was released, and the user was notified."
	):
		assert consumer.n8n_client.fire.await_count == 1
		consumer.n8n_queue.release.assert_awaited_once()
		mock_broadcast.assert_awaited_once_with(_MSG_AGENT_ERROR, "alert")
		mock_fire_pending.assert_awaited_once()


# ---------------------------------------------------------------------------
# _fire_pending_if_any
# ---------------------------------------------------------------------------


def test_fire_pending_if_any_noop_when_nothing_queued():
	"""Test _fire_pending_if_any is a no-op when nothing is queued"""

	with step("Arrange: A consumer whose queue has nothing pending."):
		consumer = _make_consumer()
		consumer.n8n_queue = MagicMock(pop_pending=AsyncMock(return_value=None))

	with step("Act: Call _fire_pending_if_any."):
		fire = consumer._fire_pending_if_any  # pylint: disable=protected-access
		async_to_sync(fire)()

	with step("Assert: pop_pending was checked and nothing else happened."):
		consumer.n8n_queue.pop_pending.assert_awaited_once()


def test_fire_pending_if_any_fires_when_pending_exists(mocker):
	"""Test _fire_pending_if_any fires the queued message once the lock is acquired"""

	with step("Arrange: A consumer with a pending message and a free lock."):
		consumer = _make_consumer()
		pending = {"expertise_level": 3, "message": "queued"}
		consumer.n8n_queue = MagicMock(
			pop_pending=AsyncMock(return_value=pending),
			try_start=AsyncMock(return_value=True),
		)
		mock_fire = mocker.patch.object(consumer, "_fire_n8n", AsyncMock())

	with step("Act: Call _fire_pending_if_any."):
		fire = consumer._fire_pending_if_any  # pylint: disable=protected-access
		async_to_sync(fire)()

	with step("Assert: The queued message was fired."):
		mock_fire.assert_called_once_with("queued", expertise_level=3)


def test_fire_pending_if_any_requeues_when_lock_lost():
	"""Test _fire_pending_if_any puts the message back if it loses the race for the lock"""

	with step("Arrange: A consumer with a pending message and a lock held elsewhere."):
		consumer = _make_consumer()
		pending = {"expertise_level": 2, "message": "queued"}
		consumer.n8n_queue = MagicMock(
			pop_pending=AsyncMock(return_value=pending),
			set_pending=AsyncMock(),
			try_start=AsyncMock(return_value=False),
		)

	with step("Act: Call _fire_pending_if_any."):
		fire = consumer._fire_pending_if_any  # pylint: disable=protected-access
		async_to_sync(fire)()

	with step("Assert: The message was put back into the pending slot."):
		consumer.n8n_queue.set_pending.assert_awaited_once_with(pending)


# ---------------------------------------------------------------------------
# set_processes
# ---------------------------------------------------------------------------


def test_set_processes_stores_event_processes():
	"""Test set_processes stores the process list carried by the channel-layer event"""

	with step("Arrange: A consumer and a set_processes event."):
		consumer = _make_consumer()

	with step("Act: Call set_processes."):
		async_to_sync(consumer.set_processes)({"processes": [{"name": "x"}]})

	with step("Assert: pending_processes was stored."):
		assert consumer.pending_processes == [{"name": "x"}]


# ---------------------------------------------------------------------------
# resolve_context — resume branch
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_resolve_context_restores_n8n_state_for_a_resumed_session():
	"""Test resolve_context loads the resumed session and restores its saved n8n state"""

	with step("Arrange: A persisted session carrying saved n8n state."):
		org = _make_org()
		session = MChatSession.objects.create(
			connection_key="TESTDB",
			n8n_state={"process_id": 5},
			org=org,
			username="bob",
		)
		consumer = CChat()
		consumer.scope = {"organization": org}
		consumer.user = MagicMock(
			session=MagicMock(connection_key="TESTDB"), username="bob"
		)
		consumer._resume_session_id = session.id  # pylint: disable=protected-access

	with step("Act: Call resolve_context with the n8n Redis helpers mocked out."):
		with patch("web_socket.consumers.chat.N8nClient"), patch(
			"web_socket.consumers.chat.N8nQueueState"
		), patch("web_socket.consumers.chat.N8nSessionState") as mock_state:
			mock_state.return_value.restore = AsyncMock()
			mock_state.return_value.clear = AsyncMock()
			async_to_sync(consumer.resolve_context)()

	with step("Assert: The session was loaded and its state restored."):
		assert consumer.chat_session.id == session.id
		mock_state.return_value.restore.assert_awaited_once_with({"process_id": 5})


@pytest.mark.django_db(transaction=True)
def test_resolve_context_resume_session_not_found_skips_restore():
	"""Test resolve_context leaves chat_session unset when the resumed session can't be found"""

	with step("Arrange: A resume id with no matching session."):
		org = _make_org()
		consumer = CChat()
		consumer.scope = {"organization": org}
		consumer.user = MagicMock(
			session=MagicMock(connection_key="TESTDB"), username="bob"
		)
		consumer._resume_session_id = 9999999  # pylint: disable=protected-access

	with step("Act: Call resolve_context with the n8n Redis helpers mocked out."):
		with patch("web_socket.consumers.chat.N8nClient"), patch(
			"web_socket.consumers.chat.N8nQueueState"
		), patch("web_socket.consumers.chat.N8nSessionState") as mock_state:
			mock_state.return_value.restore = AsyncMock()
			mock_state.return_value.clear = AsyncMock()
			async_to_sync(consumer.resolve_context)()

	with step("Assert: No session was resolved and no state restore was attempted."):
		assert consumer.chat_session is None
		mock_state.return_value.restore.assert_not_awaited()


# ---------------------------------------------------------------------------
# websocket_disconnect
# ---------------------------------------------------------------------------


def test_websocket_disconnect_closes_redis_helpers(mocker):
	"""Test websocket_disconnect closes both Redis helpers before delegating to the parent"""

	with step("Arrange: A consumer with live n8n_state/n8n_queue and a mocked parent."):
		consumer = _make_consumer()
		consumer.n8n_state = MagicMock(close=AsyncMock())
		consumer.n8n_queue = MagicMock(close=AsyncMock())
		mock_super = mocker.patch(
			"channels.generic.websocket.AsyncWebsocketConsumer.websocket_disconnect",
			AsyncMock(),
		)

	with step("Act: Call websocket_disconnect."):
		async_to_sync(consumer.websocket_disconnect)({"code": 1000})

	with step("Assert: Both helpers were closed and the parent was delegated to."):
		consumer.n8n_state.close.assert_awaited_once()
		consumer.n8n_queue.close.assert_awaited_once()
		mock_super.assert_awaited_once()


def test_websocket_disconnect_skips_helpers_never_initialised(mocker):
	"""Test websocket_disconnect tolerates n8n_state/n8n_queue never having been set up"""

	with step("Arrange: A consumer whose Redis helpers were never initialised."):
		consumer = _make_consumer()
		consumer.n8n_state = None
		consumer.n8n_queue = None
		mock_super = mocker.patch(
			"channels.generic.websocket.AsyncWebsocketConsumer.websocket_disconnect",
			AsyncMock(),
		)

	with step("Act: Call websocket_disconnect."):
		async_to_sync(consumer.websocket_disconnect)({"code": 1000})

	with step("Assert: The parent was still delegated to, without error."):
		mock_super.assert_awaited_once()
