"""Web Socket module"""

# Libs imports
from django.urls import re_path


def get_websocket_urlpatterns():
	"""Helper to set websocket url patterns"""
	# Ensure django app is loaded
	# pylint: disable=import-outside-toplevel
	from web_socket.consumers import CChat

	return [
		re_path(
			r"ws/chat/$",
			CChat.as_asgi(),
		),
	]
