"""This module contains tests for the Redis-backed n8n session state machine"""

# General imports
from unittest.mock import AsyncMock
from uuid import uuid4

# Lib imports
from allure import step
from asgiref.sync import async_to_sync

# App imports
from web_socket.helpers.n8n.state import N8nSessionState


def test_load_returns_empty_dict_when_nothing_saved():
	"""Test load returns an empty dict when no state was ever saved"""

	with step("Arrange: A fresh group with no saved state."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			try:
				return await state.load()
			finally:
				await state.close()

	with step("Act: Call load."):
		result = async_to_sync(_act)()

	with step("Assert: An empty dict is returned."):
		assert result == {}


def test_load_swallows_redis_errors_and_returns_empty_dict():
	"""Test load returns an empty dict (not raise) when Redis itself errors out"""

	with step("Arrange: A state whose Redis client raises on get()."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			state._redis.get = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			return await state.load()

	with step("Act: Call load."):
		result = async_to_sync(_act)()

	with step("Assert: An empty dict is returned instead of raising."):
		assert result == {}


def test_save_and_load_round_trip():
	"""Test save persists a full state dict that load later returns"""

	with step("Arrange: A group and a full state payload."):
		group_name = f"test_{uuid4()}"

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.save(
					active_node_id="n1",
					awaiting_batch_confirmation=True,
					awaiting_stack_resume=True,
					form_state={"field": "value"},
					intention_nodes=[{"id": "n1", "status": "active"}],
					last_bot_message="hi",
					parent_override_id="n0#0",
					paused_node_ids=["n0"],
					pending_batch_items=[{"process_name": "Create Purchase Request"}],
					pending_processes=[{"name": "x"}],
					process_definition={"name": "Create PO"},
					process_id=5,
					process_stack=[1, 2],
				)
				return await state.load()
			finally:
				await state.close()

	with step("Act: Save then load the state."):
		result = async_to_sync(_act)()

	with step("Assert: Every field survives the round trip."):
		assert result == {
			"active_node_id": "n1",
			"awaiting_batch_confirmation": True,
			"awaiting_stack_resume": True,
			"form_state": {"field": "value"},
			"intention_nodes": [{"id": "n1", "status": "active"}],
			"last_bot_message": "hi",
			"parent_override_id": "n0#0",
			"paused_node_ids": ["n0"],
			"pending_batch_items": [{"process_name": "Create Purchase Request"}],
			"pending_processes": [{"name": "x"}],
			"process_definition": {"name": "Create PO"},
			"process_id": 5,
			"process_stack": [1, 2],
		}


def test_save_defaults_process_stack_to_empty_list():
	"""Test save stores an empty list for process_stack when none is given"""

	with step("Arrange: A group and a save call with no process_stack."):
		group_name = f"test_{uuid4()}"

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.save()
				return await state.load()
			finally:
				await state.close()

	with step("Act: Save then load the state."):
		result = async_to_sync(_act)()

	with step("Assert: process_stack defaults to an empty list."):
		assert result["process_stack"] == []


def test_save_defaults_intention_node_fields():
	"""Test save stores empty lists for intention_nodes/paused_node_ids and None for active_node_id by default"""

	with step("Arrange: A group and a save call with no intention-graph fields."):
		group_name = f"test_{uuid4()}"

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.save()
				return await state.load()
			finally:
				await state.close()

	with step("Act: Save then load the state."):
		result = async_to_sync(_act)()

	with step(
		"Assert: intention_nodes/paused_node_ids default to [], active_node_id to None."
	):
		assert result["intention_nodes"] == []
		assert result["paused_node_ids"] == []
		assert result["active_node_id"] is None
		assert result["parent_override_id"] is None


def test_save_defaults_batch_confirmation_fields():
	"""Test save stores False for awaiting_batch_confirmation and None for pending_batch_items by default"""

	with step("Arrange: A group and a save call with no batch-confirmation fields."):
		group_name = f"test_{uuid4()}"

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.save()
				return await state.load()
			finally:
				await state.close()

	with step("Act: Save then load the state."):
		result = async_to_sync(_act)()

	with step(
		"Assert: awaiting_batch_confirmation is False and pending_batch_items is an empty list."
	):
		assert result["awaiting_batch_confirmation"] is False
		assert result["pending_batch_items"] == []


def test_save_swallows_redis_errors():
	"""Test save does not raise when Redis itself errors out"""

	with step("Arrange: A state whose Redis client raises on set()."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			state._redis.set = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await state.save()

	with step("Act/Assert: save does not raise."):
		async_to_sync(_act)()


def test_restore_writes_state_that_load_then_returns():
	"""Test restore writes a saved state dict directly, readable back via load"""

	with step("Arrange: A group and a state dict to restore."):
		group_name = f"test_{uuid4()}"
		saved_state = {"process_id": 9}

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.restore(saved_state)
				return await state.load()
			finally:
				await state.close()

	with step("Act: Restore then load the state."):
		result = async_to_sync(_act)()

	with step("Assert: The restored state is returned unchanged."):
		assert result == saved_state


def test_restore_swallows_redis_errors():
	"""Test restore does not raise when Redis itself errors out"""

	with step("Arrange: A state whose Redis client raises on set()."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			state._redis.set = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await state.restore({"process_id": 1})

	with step("Act/Assert: restore does not raise."):
		async_to_sync(_act)()


def test_clear_deletes_the_state_key():
	"""Test clear removes the state so a subsequent load finds nothing"""

	with step("Arrange: A group with a saved state."):
		group_name = f"test_{uuid4()}"

		async def _seed():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.save(process_id=1)
			finally:
				await state.close()

		async_to_sync(_seed)()

		async def _act():
			state = N8nSessionState(group_name=group_name)
			try:
				await state.clear()
				return await state.load()
			finally:
				await state.close()

	with step("Act: Clear then load the state."):
		result = async_to_sync(_act)()

	with step("Assert: The state was cleared."):
		assert result == {}


def test_clear_swallows_redis_errors():
	"""Test clear does not raise when Redis itself errors out"""

	with step("Arrange: A state whose Redis client raises on delete()."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			state._redis.delete = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await state.clear()

	with step("Act/Assert: clear does not raise."):
		async_to_sync(_act)()


def test_close_swallows_redis_errors():
	"""Test close does not raise when the underlying Redis pool fails to close cleanly"""

	with step("Arrange: A state whose Redis client raises on aclose()."):

		async def _act():
			state = N8nSessionState(group_name=f"test_{uuid4()}")
			state._redis.aclose = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await state.close()

	with step("Act/Assert: close does not raise."):
		async_to_sync(_act)()
