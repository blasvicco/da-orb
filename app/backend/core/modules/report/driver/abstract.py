"""Report driver base"""

# General imports
from abc import ABC, abstractmethod


# pylint: disable=too-few-public-methods
class AReport(ABC):
	"""Abstract report-rendering driver — all drivers must implement render()."""

	@abstractmethod
	def render(self, template_path: str, data: dict) -> str:
		"""Render template_path against data and return the local path to the rendered PDF."""
