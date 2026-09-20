"""This module contains tests for the recursive n8n execution-tree token usage walk"""

# General imports
from unittest.mock import MagicMock, patch

# Lib imports
import httpx
from allure import step

# App imports
from web_socket.helpers.n8n.usage import collect_execution_tree_usage


def _make_response(payload):
	"""Build a mocked httpx.Response-like object returning the given JSON payload"""
	response = MagicMock()
	response.json.return_value = payload
	response.raise_for_status = MagicMock()
	return response


def _run_entry(
	*,
	completion_tokens=None,
	prompt_tokens=None,
	sub_execution_id=None,
	total_tokens=None
):
	"""Build one runData run entry, optionally carrying Chat Model usage and/or a spawned sub-execution"""
	entry = {"data": {"main": [[]]}, "metadata": {}}
	if sub_execution_id is not None:
		entry["metadata"]["subExecution"] = {"executionId": sub_execution_id}
	if total_tokens is not None:
		entry["data"]["ai_languageModel"] = [
			[
				{
					"json": {
						"tokenUsageEstimate": {
							"completionTokens": completion_tokens,
							"promptTokens": prompt_tokens,
							"totalTokens": total_tokens,
						}
					}
				}
			]
		]
	return entry


def test_collect_execution_tree_usage_sums_a_single_finished_execution():
	"""Test collect_execution_tree_usage sums Chat Model usage from one finished execution's own run data"""

	with step("Arrange: A finished execution with one Chat Model run entry."):
		execution = {
			"data": {
				"resultData": {
					"runData": {
						"OpenAI Chat Model Find": [
							_run_entry(
								completion_tokens=7,
								prompt_tokens=2273,
								total_tokens=2280,
							)
						]
					}
				}
			},
			"finished": True,
			"id": "100",
		}

	with step("Act: Call collect_execution_tree_usage."):
		with patch(
			"web_socket.helpers.n8n.usage.httpx.get",
			return_value=_make_response(execution),
		):
			result = collect_execution_tree_usage("100")

	with step("Assert: The totals match the single run entry."):
		assert result == {
			"completion_tokens": 7,
			"prompt_tokens": 2273,
			"total_tokens": 2280,
		}


def test_collect_execution_tree_usage_recurses_into_child_executions():
	"""Test collect_execution_tree_usage follows metadata.subExecution.executionId and sums the whole tree"""

	with step(
		"Arrange: A root execution whose call site spawned a child with its own usage."
	):
		root = {
			"data": {
				"resultData": {
					"runData": {
						"Agent: Intent Finder": [_run_entry(sub_execution_id="200")]
					}
				}
			},
			"finished": True,
			"id": "100",
		}
		child = {
			"data": {
				"resultData": {
					"runData": {
						"OpenAI Chat Model Find": [
							_run_entry(
								completion_tokens=7,
								prompt_tokens=2273,
								total_tokens=2280,
							)
						]
					}
				}
			},
			"finished": True,
			"id": "200",
		}

	with step("Act: Call collect_execution_tree_usage."):
		with patch(
			"web_socket.helpers.n8n.usage.httpx.get",
			side_effect=[_make_response(root), _make_response(child)],
		):
			result = collect_execution_tree_usage("100")

	with step(
		"Assert: The child's usage was picked up even though the root itself had none."
	):
		assert result == {
			"completion_tokens": 7,
			"prompt_tokens": 2273,
			"total_tokens": 2280,
		}


def test_collect_execution_tree_usage_sums_multiple_runs_of_the_same_node():
	"""Test collect_execution_tree_usage sums every run entry for a node that executed more than once (a loop)"""

	with step("Arrange: A finished execution whose Chat Model node ran twice."):
		execution = {
			"data": {
				"resultData": {
					"runData": {
						"OpenAI Chat Model": [
							_run_entry(
								completion_tokens=50,
								prompt_tokens=400,
								total_tokens=450,
							),
							_run_entry(
								completion_tokens=45,
								prompt_tokens=380,
								total_tokens=425,
							),
						]
					}
				}
			},
			"finished": True,
			"id": "100",
		}

	with step("Act: Call collect_execution_tree_usage."):
		with patch(
			"web_socket.helpers.n8n.usage.httpx.get",
			return_value=_make_response(execution),
		):
			result = collect_execution_tree_usage("100")

	with step("Assert: Both runs' usage was added together."):
		assert result == {
			"completion_tokens": 95,
			"prompt_tokens": 780,
			"total_tokens": 875,
		}


def test_collect_execution_tree_usage_returns_none_when_no_usage_found():
	"""Test collect_execution_tree_usage returns None (not zeros) when the tree carries no Chat Model usage at all"""

	with step(
		"Arrange: A finished execution with run data but no ai_languageModel output."
	):
		execution = {
			"data": {"resultData": {"runData": {"Some Node": [_run_entry()]}}},
			"finished": True,
			"id": "100",
		}

	with step("Act: Call collect_execution_tree_usage."):
		with patch(
			"web_socket.helpers.n8n.usage.httpx.get",
			return_value=_make_response(execution),
		):
			result = collect_execution_tree_usage("100")

	with step("Assert: None is returned."):
		assert result is None


def test_collect_execution_tree_usage_returns_none_when_never_finished():
	"""Test collect_execution_tree_usage gives up and returns None once the poll timeout elapses"""

	with step("Arrange: An execution that always reports still running."):
		still_running = {"data": {}, "finished": False, "id": "100"}

	with step(
		"Act: Call collect_execution_tree_usage with the poll window shrunk so the "
		"test doesn't actually wait out the real 30s timeout."
	):
		with patch("web_socket.helpers.n8n.usage._POLL_TIMEOUT_SECONDS", 0.05), patch(
			"web_socket.helpers.n8n.usage._POLL_INTERVAL_SECONDS", 0.01
		), patch(
			"web_socket.helpers.n8n.usage.httpx.get",
			return_value=_make_response(still_running),
		):
			result = collect_execution_tree_usage("100")

	with step("Assert: None is returned rather than hanging or raising."):
		assert result is None


def test_collect_execution_tree_usage_returns_none_when_fetch_fails():
	"""Test collect_execution_tree_usage returns None when n8n's REST API itself errors out"""

	with step("Arrange: An httpx.get that always raises."):

		def _raise(*_args, **_kwargs):
			raise httpx.HTTPError("boom")

	with step(
		"Act: Call collect_execution_tree_usage with the poll window shrunk so the "
		"test doesn't actually wait out the real 30s timeout."
	):
		with patch("web_socket.helpers.n8n.usage._POLL_TIMEOUT_SECONDS", 0.05), patch(
			"web_socket.helpers.n8n.usage._POLL_INTERVAL_SECONDS", 0.01
		), patch("web_socket.helpers.n8n.usage.httpx.get", side_effect=_raise):
			result = collect_execution_tree_usage("100")

	with step("Assert: None is returned rather than raising."):
		assert result is None
