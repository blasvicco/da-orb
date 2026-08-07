"""Storage driver base"""

# General imports
from abc import ABC, abstractmethod


class AStorage(ABC):
	"""Abstract object-storage driver — all drivers must implement delete(), presigned_url(), and upload()."""

	@abstractmethod
	def delete(self, dest_path: str) -> None:
		"""Delete the object at dest_path from the storage backend."""

	@abstractmethod
	def presigned_url(self, dest_path: str, expires_in: int) -> str:
		"""Return a presigned GET URL for dest_path, valid for expires_in seconds."""

	@abstractmethod
	def upload(self, src_path: str, dest_path: str, content_type: str) -> None:
		"""Upload the file at src_path to dest_path on the storage backend."""
