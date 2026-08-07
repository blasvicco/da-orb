"""Seat reactions to auth-domain events"""

# App imports
from core.modules.hooks import Hooks
from drf_api.models import MSeat

Hooks.add_listener("user_authenticated", MSeat.provision_or_check_seat)
