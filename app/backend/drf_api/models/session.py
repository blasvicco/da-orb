"""Auth session model"""
# General imports
import uuid

class MSession:
	"""In-memory representation of an authenticated session."""

	access_token = ""
	database = ""
	expires_at = 0
	id_token = ""
	language = "es"
	org = ""
	refresh_token = ""
	user = None

	def __init__(self, **kwargs):
		"""Initialise the session."""
		self.access_token = kwargs.get("access_token", "")
		self.database = kwargs.get("database", "")
		self.expires_at = int(kwargs.get("expires_at", 0))
		self.id_token = kwargs.get("id_token", "") or str(uuid.uuid4())
		self.language = kwargs.get("language", "es")
		self.org = kwargs.get("org", "")
		self.refresh_token = kwargs.get("refresh_token", "")
		self.user = kwargs.get("user") or {
			"username": "",
			"password": kwargs.get("password", ""),
		}

	def to_dict(self) -> dict:
		"""Return dictionary representation of the session."""
		return {
			"access_token": self.access_token,
			"database": self.database,
			"expires_at": self.expires_at,
			"id_token": self.id_token,
			"language": self.language,
			"org": self.org,
			"refresh_token": self.refresh_token,
			"user": {
				"username": self.user.get("username", ""),
				"password": self.user.get("password", ""),
			},
		}
