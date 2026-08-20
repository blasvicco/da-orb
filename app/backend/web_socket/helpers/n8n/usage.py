"""n8n Usage Collector — walks a finished execution tree via n8n's own REST API and sums token usage"""

# General imports
import logging
import time

# Lib imports
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 1.5
_POLL_TIMEOUT_SECONDS = 30
_REQUEST_TIMEOUT_SECONDS = 15


def collect_execution_tree_usage(root_execution_id: str) -> dict | None:
	"""Poll the root execution until it finishes, then walk its whole tree and sum every Chat Model call's token usage."""
	# n8n's executions API only exposes runData once an execution genuinely reports
	# finished — a node querying its own still-running execution always sees it empty
	# (confirmed live, under this deployment's EXECUTIONS_MODE=queue). The turn is only
	# reported to Django once response.json's own delivery step runs, which happens
	# while the root (spine) execution is still nested several calls deep — so this has
	# to poll for a moment after being triggered, not assume the tree is already done.
	execution = _wait_for_finished(root_execution_id)
	if execution is None:
		logger.warning(
			"collect_execution_tree_usage: execution %s never reported finished within %ss",
			root_execution_id,
			_POLL_TIMEOUT_SECONDS,
		)
		return None
	totals = {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0}
	_accumulate_execution_tree(execution, totals, seen=set())
	return totals if totals["total_tokens"] > 0 else None


def _accumulate_execution_tree(execution, totals, seen):
	"""Sum token usage from this execution's own run data, then recurse into every child execution it spawned."""
	execution_id = execution.get("id")
	if execution_id in seen:
		return
	seen.add(execution_id)
	run_data = (execution.get("data") or {}).get("resultData", {}).get("runData", {})
	child_execution_ids = []
	for runs in run_data.values():
		for run in runs:
			# An Execute Workflow node's own run entry records what it spawned here —
			# this is what makes the whole tree walkable without knowing its shape in
			# advance: every nested sub-workflow call site carries this, regardless of
			# which file it lives in or how deep it's nested.
			sub_execution = (run.get("metadata") or {}).get("subExecution") or {}
			if sub_execution.get("executionId"):
				child_execution_ids.append(sub_execution["executionId"])
			usage = _extract_usage(run)
			if usage:
				totals["completion_tokens"] += usage["completion_tokens"]
				totals["prompt_tokens"] += usage["prompt_tokens"]
				totals["total_tokens"] += usage["total_tokens"]
	for child_execution_id in child_execution_ids:
		child_execution = _fetch_execution(child_execution_id)
		if child_execution is not None:
			_accumulate_execution_tree(child_execution, totals, seen)


def _extract_usage(run):
	"""Return {completion_tokens, prompt_tokens, total_tokens} from a run entry's ai_languageModel output, if present."""
	# A Chat Model node only ever outputs on the ai_languageModel connection type, never
	# main — n8n's in-process $('NodeName') accessor can't reach it at all (confirmed
	# live: "No data found from `main` input"), but the stored execution record still
	# carries it here regardless of connection type.
	branches = (run.get("data") or {}).get("ai_languageModel") or [[]]
	for item in branches[0] if branches else []:
		payload = (item or {}).get("json") or {}
		usage = payload.get("tokenUsageEstimate") or payload.get("tokenUsage")
		if usage:
			return {
				"completion_tokens": usage.get(
					"completionTokens", usage.get("completion_tokens", 0)
				)
				or 0,
				"prompt_tokens": usage.get(
					"promptTokens", usage.get("prompt_tokens", 0)
				)
				or 0,
				"total_tokens": usage.get("totalTokens", usage.get("total_tokens", 0))
				or 0,
			}
	return None


def _fetch_execution(execution_id):
	"""GET one execution's full data from n8n's REST API, or None on failure."""
	try:
		response = httpx.get(
			f"{settings.N8N_API_BASE_URL}/executions/{execution_id}",
			headers={"X-N8N-API-KEY": settings.N8N_API_KEY},
			params={"includeData": "true"},
			timeout=_REQUEST_TIMEOUT_SECONDS,
		)
		response.raise_for_status()
		return response.json()
	except httpx.HTTPError:
		logger.exception("_fetch_execution: failed to fetch execution %s", execution_id)
		return None


def _wait_for_finished(execution_id):
	"""Poll one execution until it reports finished, or return None once the timeout elapses."""
	deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
	while time.monotonic() < deadline:
		execution = _fetch_execution(execution_id)
		if execution is not None and execution.get("finished"):
			return execution
		time.sleep(_POLL_INTERVAL_SECONDS)
	return None
