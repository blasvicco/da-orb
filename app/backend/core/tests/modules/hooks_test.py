"""This module contains tests for the shared hook/event registry"""

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.hooks import Hooks


@pytest.fixture(autouse=True)
def _reset_listeners():
	"""Hooks.listeners is process-global state — isolate each test from the others."""
	original = Hooks.listeners
	Hooks.listeners = {}
	yield
	Hooks.listeners = original


def test_get_listeners_returns_empty_list_for_an_unregistered_event():
	"""Test get_listeners returns [] when nothing was ever registered for the event"""

	with step("Act: Call get_listeners for an event with no listeners."):
		result = Hooks.get_listeners("does_not_exist")

	with step("Assert: An empty list is returned."):
		assert not result


def test_add_listener_registers_method_and_args():
	"""Test add_listener stores the method together with its args/kwargs"""

	with step("Arrange: A plain callable."):
		calls = []
		method = calls.append

	with step("Act: Register it for an event, with extra args/kwargs."):
		Hooks.add_listener("thing_happened", method, "arg1", kwarg1="value1")

	with step("Assert: get_listeners returns the method and its bound args/kwargs."):
		[registered] = Hooks.get_listeners("thing_happened")
		assert registered == [method, ("arg1",), {"kwarg1": "value1"}]


def test_add_listener_supports_multiple_listeners_for_the_same_event():
	"""Test add_listener appends rather than overwrites when called more than once"""

	with step("Arrange: Two distinct callables."):
		first_calls, second_calls = [], []

	with step("Act: Register both for the same event."):
		Hooks.add_listener("thing_happened", first_calls.append)
		Hooks.add_listener("thing_happened", second_calls.append)

	with step("Assert: Both are returned, in registration order."):
		methods = [entry[0] for entry in Hooks.get_listeners("thing_happened")]
		assert methods == [first_calls.append, second_calls.append]


def test_listeners_for_different_events_do_not_interfere():
	"""Test add_listener/get_listeners scope listeners strictly per event_name"""

	with step("Arrange: Two callables registered under different event names."):
		calls_a, calls_b = [], []
		method_a, method_b = calls_a.append, calls_b.append
		Hooks.add_listener("event_a", method_a)
		Hooks.add_listener("event_b", method_b)

	with step("Act: Call get_listeners for event_a."):
		result = Hooks.get_listeners("event_a")

	with step("Assert: Only event_a's listener is returned."):
		assert [entry[0] for entry in result] == [method_a]
