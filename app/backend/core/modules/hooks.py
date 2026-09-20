"""Custom hook class"""


class Hooks:
	"""Simple event registry, avoiding a direct import dependency in either direction between the announcer and its listeners."""

	# A listener is registered by importing its module once (see
	# drf_api/resources/seat/__init__.py for the pattern), so registration itself
	# must never touch anything not safe to import at that point (e.g. models) —
	# only the listener function's own body, called later, may do that.

	listeners = {}

	@staticmethod
	def add_listener(event_name, method, *args, **kwargs):
		"""Add event listener"""
		Hooks.listeners[event_name] = Hooks.listeners.get(event_name) or []
		Hooks.listeners[event_name].append([method, args, kwargs])

	@staticmethod
	def get_listeners(event_name):
		"""Get all the listeners of the given event"""
		return Hooks.listeners.get(event_name) or []
