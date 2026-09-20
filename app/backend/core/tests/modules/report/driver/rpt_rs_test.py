"""This module contains tests for the rpt_rs report-rendering driver"""

# General imports
import json
import subprocess

# Lib imports
import pytest
from allure import step

# App imports
from core.modules.report.driver.rpt_rs import Instance
from core.modules.report.exception import ReportError


def test_render(mocker, settings):
	"""Test render() writes data as JSON, shells out to REPORT_RENDER_BINARY, and returns the output path"""

	with step("Arrange: An Instance with subprocess.run mocked."):
		settings.REPORT_RENDER_BINARY = "/usr/local/bin/orb-report-render"
		mock_run = mocker.patch("core.modules.report.driver.rpt_rs.subprocess.run")
		instance = Instance()
		data = {"rows": [{"InvoiceNumber": "12345"}]}

	with step("Act: Call render."):
		output_path = instance.render("/templates/invoice_default.rpt", data)

	with step(
		"Assert: subprocess.run called with the binary, template, data file, and output path."
	):
		call_args = mock_run.call_args[0][0]
		assert call_args[0] == "/usr/local/bin/orb-report-render"
		assert call_args[1] == "/templates/invoice_default.rpt"
		assert call_args[3] == output_path
		with open(call_args[2], encoding="utf-8") as data_file:
			assert json.load(data_file) == data


def test_render_wraps_process_errors(mocker, settings):
	"""Test render() wraps a non-zero exit as ReportError"""

	with step("Arrange: An Instance whose subprocess.run raises CalledProcessError."):
		settings.REPORT_RENDER_BINARY = "/usr/local/bin/orb-report-render"
		mocker.patch(
			"core.modules.report.driver.rpt_rs.subprocess.run",
			side_effect=subprocess.CalledProcessError(
				1, "orb-report-render", stderr=b"bad template"
			),
		)
		instance = Instance()

	with step("Act & Assert: ReportError is raised."):
		with pytest.raises(ReportError, match="bad template"):
			instance.render("/templates/invoice_default.rpt", {"rows": []})


def test_render_wraps_timeout(mocker, settings):
	"""Test render() wraps a timeout as ReportError"""

	with step("Arrange: An Instance whose subprocess.run times out."):
		settings.REPORT_RENDER_BINARY = "/usr/local/bin/orb-report-render"
		mocker.patch(
			"core.modules.report.driver.rpt_rs.subprocess.run",
			side_effect=subprocess.TimeoutExpired("orb-report-render", 60),
		)
		instance = Instance()

	with step("Act & Assert: ReportError is raised."):
		with pytest.raises(ReportError, match="timed out"):
			instance.render("/templates/invoice_default.rpt", {"rows": []})
