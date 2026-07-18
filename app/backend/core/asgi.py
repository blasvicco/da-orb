"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

This is used ONLY for WebSockets (Django Channels).
"""

# General imports
import os

# Libs imports
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# Initialize Django first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django_asgi_app = get_asgi_application()

# App imports
# pylint: disable=wrong-import-position
from web_socket.middleware.oauth2 import MOAuth2
from web_socket.routing import get_websocket_urlpatterns

application = ProtocolTypeRouter(
	{
		"http": django_asgi_app,
		"websocket": MOAuth2(URLRouter(get_websocket_urlpatterns())),
	}
)
