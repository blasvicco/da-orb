"""rpt-rs report-rendering driver"""

# General imports
import json
import subprocess
import tempfile

# Lib imports
from django.conf import settings

# App imports
from core.modules.report.driver.abstract import AReport
from core.modules.report.exception import ReportError

_RENDER_TIMEOUT_SECONDS = 60


# pylint: disable=too-few-public-methods
class Instance(AReport):
	"""Driver implementation shelling out to the orb-report-render binary (built from app/renderer)."""

	def render(self, template_path, data):
		"""Render template_path against data (already `{"rows": [...]}`-shaped) via orb-report-render."""
		with tempfile.NamedTemporaryFile(
			mode="w", suffix=".json", delete=False
		) as data_file:
			json.dump(data, data_file)
			data_path = data_file.name
		output_path = tempfile.mktemp(suffix=".pdf")
		try:
			subprocess.run(
				[settings.REPORT_RENDER_BINARY, template_path, data_path, output_path],
				capture_output=True,
				check=True,
				timeout=_RENDER_TIMEOUT_SECONDS,
			)
		except subprocess.CalledProcessError as error:
			raise ReportError(
				f"Render failed for '{template_path}': {error.stderr.decode(errors='replace')}"
			) from error
		except subprocess.TimeoutExpired as error:
			raise ReportError(f"Render timed out for '{template_path}'") from error
		return output_path
