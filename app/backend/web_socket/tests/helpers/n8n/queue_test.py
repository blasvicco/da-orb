"""This module contains tests for the Redis-backed n8n in-flight queue"""

# General imports
from unittest.mock import AsyncMock
from uuid import uuid4

# Lib imports
from allure import step
from asgiref.sync import async_to_sync

# App imports
from web_socket.helpers.n8n.queue import N8nQueueState


def test_try_start_acquires_a_free_lock():
	"""Test try_start returns True and acquires the lock when it is free"""

	with step("Arrange: A fresh group_name with no lock held."):
		group_name = f"test_{uuid4()}"

		async def _act():
			queue = N8nQueueState(group_name=group_name)
			try:
				return await queue.try_start()
			finally:
				await queue.close()

	with step("Act: Call try_start."):
		acquired = async_to_sync(_act)()

	with step("Assert: The lock was acquired."):
		assert acquired is True


def test_try_start_fails_when_already_held():
	"""Test try_start returns False when another execution already holds the lock"""

	with step("Arrange: A group whose lock is already held."):
		group_name = f"test_{uuid4()}"

		async def _hold():
			queue = N8nQueueState(group_name=group_name)
			try:
				await queue.try_start()
			finally:
				await queue.close()

		async_to_sync(_hold)()

		async def _act():
			queue = N8nQueueState(group_name=group_name)
			try:
				return await queue.try_start()
			finally:
				await queue.close()

	with step("Act: Call try_start again for the same group."):
		acquired = async_to_sync(_act)()

	with step("Assert: The second attempt fails to acquire the lock."):
		assert acquired is False


def test_try_start_fails_open_on_redis_error():
	"""Test try_start returns True (fail open) when Redis itself errors out"""

	with step("Arrange: A queue whose Redis client raises on set()."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			queue._redis.set = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			return await queue.try_start()

	with step("Act: Call try_start."):
		acquired = async_to_sync(_act)()

	with step("Assert: True is returned so a Redis outage never blocks the user."):
		assert acquired is True


def test_release_clears_the_lock():
	"""Test release deletes the in-flight lock so a subsequent try_start can succeed"""

	with step("Arrange: A group whose lock is held."):
		group_name = f"test_{uuid4()}"

		async def _hold():
			queue = N8nQueueState(group_name=group_name)
			try:
				await queue.try_start()
			finally:
				await queue.close()

		async_to_sync(_hold)()

		async def _release():
			queue = N8nQueueState(group_name=group_name)
			try:
				await queue.release()
			finally:
				await queue.close()

	with step("Act: Call release."):
		async_to_sync(_release)()

	with step("Assert: A fresh try_start (same group) can acquire the lock again."):

		async def _retry():
			queue = N8nQueueState(group_name=group_name)
			try:
				return await queue.try_start()
			finally:
				await queue.close()

		assert async_to_sync(_retry)() is True


def test_release_swallows_redis_errors():
	"""Test release does not raise when Redis itself errors out"""

	with step("Arrange: A queue whose Redis client raises on delete()."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			queue._redis.delete = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await queue.release()

	with step("Act/Assert: release does not raise."):
		async_to_sync(_act)()


def test_set_pending_and_pop_pending_round_trip():
	"""Test set_pending stores a payload that pop_pending later returns and clears"""

	with step("Arrange: A payload to queue."):
		payload = {"message": "hello"}

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			try:
				await queue.set_pending(payload)
				first = await queue.pop_pending()
				second = await queue.pop_pending()
				return first, second
			finally:
				await queue.close()

	with step("Act: Set then pop the pending payload twice."):
		first, second = async_to_sync(_act)()

	with step("Assert: The first pop returns the payload, the second finds nothing."):
		assert first == payload
		assert second is None


def test_pop_pending_returns_none_when_nothing_queued():
	"""Test pop_pending returns None when no message was ever queued"""

	with step("Arrange: A fresh group with nothing pending."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			try:
				return await queue.pop_pending()
			finally:
				await queue.close()

	with step("Act: Call pop_pending."):
		result = async_to_sync(_act)()

	with step("Assert: None is returned."):
		assert result is None


def test_set_pending_swallows_redis_errors():
	"""Test set_pending does not raise when Redis itself errors out"""

	with step("Arrange: A queue whose Redis client raises on set()."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			queue._redis.set = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await queue.set_pending({"message": "hello"})

	with step("Act/Assert: set_pending does not raise."):
		async_to_sync(_act)()


def test_pop_pending_swallows_redis_errors_and_returns_none():
	"""Test pop_pending returns None (not raise) when Redis itself errors out"""

	with step("Arrange: A queue whose Redis client raises on get()."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			queue._redis.get = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			return await queue.pop_pending()

	with step("Act: Call pop_pending."):
		result = async_to_sync(_act)()

	with step("Assert: None is returned instead of raising."):
		assert result is None


def test_close_swallows_redis_errors():
	"""Test close does not raise when the underlying Redis pool fails to close cleanly"""

	with step("Arrange: A queue whose Redis client raises on aclose()."):

		async def _act():
			queue = N8nQueueState(group_name=f"test_{uuid4()}")
			queue._redis.aclose = AsyncMock(  # pylint: disable=protected-access
				side_effect=ConnectionError("boom")
			)
			await queue.close()

	with step("Act/Assert: close does not raise."):
		async_to_sync(_act)()
