"""Auth driver base"""

# General imports
from abc import ABC, abstractmethod


class AuthDriverError(Exception):
	"""Raised when an auth driver fails to authenticate or refresh."""

	def __init__(self, message, response_data=None, status_code=None):
		"""Initialize AuthDriverError."""
		super().__init__(message)
		self.response_data = response_data or {}
		self.status_code = status_code


class AAuthDriver(ABC):
	"""Abstract SAP authentication driver — all drivers must implement authenticate() and refresh()."""

	# Both methods return a normalised session dict:
	# {
	#   "access_token":  str,
	#   "expires_at":    int,  # Unix timestamp
	#   "id_token":      str,  # empty when N/A
	#   "org":           str,  # organisation slug
	#   "refresh_token": str,  # empty when N/A
	#   "user": { "email": str, "first_name": str, "last_name": str, "name": str, "username": str }
	# }

	def __init__(self, integration: dict):
		"""Initialise the driver with the organisation integration config."""
		self._integration = integration

	@abstractmethod
	def authenticate(self, **credentials) -> dict:
		"""Validate credentials and return a normalised session dict. Raises AuthDriverError on failure."""

	@abstractmethod
	def login(self, request, org: str):
		"""Process login request and return a DRF Response."""

	@abstractmethod
	def refresh(self, **token_data) -> dict:
		"""Refresh an existing session and return an updated session dict. Raises AuthDriverError on failure."""
