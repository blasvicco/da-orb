"""Thin wrapper around the n8n REST API used to run ephemeral, disposable workflow copies."""
import os
import sys
import time

import requests

# The public REST API only lives on the main process — n8n-main and n8n-webhook share the
# "n8n.blas.local" DNS alias on the docker network and round-robin between them, so hitting
# /api/v1 through that alias 404s roughly half the time. The container name is unambiguous.
API_BASE = 'http://da-orb-n8n-main:5678/api/v1'
# Webhook triggers are fine through the shared alias — this matches the URL the workflow's own
# "Self-Call Webhook" node already uses, and any instance behind it can accept the trigger.
WEBHOOK_BASE = 'http://n8n.blas.local:5678'
TERMINAL_STATUSES = {'success', 'error', 'crashed', 'canceled', 'unknown'}


class N8nClient:
	def __init__(self, api_key=None, timeout=30):
		"""Read N8N_API_KEY from the environment unless a key is passed explicitly."""
		self._headers = {'X-N8N-API-KEY': api_key or os.environ['N8N_API_KEY']}
		self._timeout = timeout

	def activate_workflow(self, workflow_id):
		"""Activate a workflow so its webhook becomes reachable."""
		self._request('post', f'{API_BASE}/workflows/{workflow_id}/activate')

	def create_workflow(self, definition):
		"""Create a workflow and return its full record, including the new id."""
		return self._request('post', f'{API_BASE}/workflows', json=definition)

	def cleanup_workflow(self, workflow_id, drain_timeout=60):
		"""Wait for any still-running executions to finish, then deactivate and delete a
		disposable test workflow, each step independent of the other's success.

		The drain step matters: if a case's own wait_for_execution gave up early (its execution
		was still genuinely running, just slow -- e.g. during a JS Task Runner slowdown), the old
		code would delete the workflow anyway once the suite finished. Confirmed live: this left
		orphaned in-flight executions with no workflow definition behind them (404 on lookup),
		which the worker then appears to retry indefinitely against a target that no longer
		exists -- a plausible driver of the repeated task-runner offer-rejection/heartbeat-failure
		spiral seen this session. Draining first means delete only ever removes a workflow with
		nothing left in flight.

		Deactivate/delete themselves already retry on transient errors (see below), but a
		*sustained* failure in one must never skip the other -- if deactivate is still down after
		its own retries, delete is the one that actually removes the orphan (a deleted workflow
		can't be active), so it's still worth attempting."""
		try:
			self._drain_executions(workflow_id, drain_timeout)
		except Exception as exc:
			print(f'warning: could not confirm executions drained for {workflow_id}, proceeding anyway: {exc}', file=sys.stderr)
		try:
			self.deactivate_workflow(workflow_id)
		except Exception as exc:
			print(f'warning: deactivate failed for {workflow_id}, attempting delete anyway: {exc}', file=sys.stderr)
		try:
			self.delete_workflow(workflow_id)
		except Exception as exc:
			print(f'warning: delete failed for {workflow_id} -- manual cleanup needed: {exc}', file=sys.stderr)

	def _drain_executions(self, workflow_id, timeout):
		"""Poll until every execution for workflow_id is in a terminal status, or give up after
		timeout (logged by the caller, not raised -- draining is a best-effort safety net, not
		something that should itself hang cleanup forever)."""
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			listing = self._request('get', f'{API_BASE}/executions', params={'workflowId': workflow_id, 'limit': 10})
			executions = listing.get('data') or []
			active = [e for e in executions if e['status'] not in TERMINAL_STATUSES]
			if not active:
				return
			time.sleep(2)
		raise TimeoutError(f'{workflow_id} still had non-terminal executions after {timeout}s')

	def deactivate_workflow(self, workflow_id, attempts=3, retry_delay=2):
		"""Deactivate a workflow before deleting it, retrying on transient errors — a disposable
		test workflow left active after a flaky call here would keep its webhook registered
		indefinitely (confirmed live: this is exactly how failed Tier 2 cleanups accumulated
		leftover __test__ workflows during a period of n8n instability)."""
		self._retry(lambda: self._request('post', f'{API_BASE}/workflows/{workflow_id}/deactivate'), attempts, retry_delay)

	def delete_workflow(self, workflow_id, attempts=3, retry_delay=2):
		"""Permanently remove a (disposable, test-only) workflow, retrying on transient errors.
		A workflow with a still-settling recursive self-call chain (see path_queue) can 500 on
		delete for a moment after its last execution finishes; a short retry clears it reliably."""
		self._retry(lambda: self._request('delete', f'{API_BASE}/workflows/{workflow_id}'), attempts, retry_delay)

	@staticmethod
	def _retry(action, attempts, retry_delay):
		# Catches the broader RequestException, not just HTTPError -- a read timeout or a
		# connection error during a transient overload never raises HTTPError at all, and would
		# otherwise skip the retry entirely (confirmed live: n8n under load returned both a 503
		# HTTPError and a plain ReadTimeout across different attempts of the same cleanup call).
		for attempt in range(attempts):
			try:
				action()
				return
			except requests.exceptions.RequestException:
				if attempt == attempts - 1:
					raise
				time.sleep(retry_delay)

	def list_workflows(self):
		"""Return every workflow's summary record, paginating through n8n's cursor-based listing."""
		results = []
		cursor = None
		while True:
			params = {'limit': 250, **({'cursor': cursor} if cursor else {})}
			page = self._request('get', f'{API_BASE}/workflows', params=params)
			results.extend(page.get('data') or [])
			cursor = page.get('nextCursor')
			if not cursor:
				return results

	def get_latest_execution_id(self, workflow_id):
		"""Snapshot the newest execution id for workflow_id, used as a baseline before triggering."""
		listing = self._request('get', f'{API_BASE}/executions', params={'workflowId': workflow_id, 'limit': 1})
		executions = listing.get('data') or []
		return int(executions[0]['id']) if executions else 0

	def get_child_execution_id(self, execution, node_name):
		"""Return the linked sub-execution id an Execute Workflow node's latest run spawned, or
		None — used to drill into a sub-workflow's own internal nodes, since the caller's own
		runData for that node only carries the sub-workflow's final output, not every node inside
		it (confirmed live: n8n embeds the final result inline AND links the full child execution
		via metadata.subExecution)."""
		run_data = execution.get('data', {}).get('resultData', {}).get('runData', {})
		runs = run_data.get(node_name)
		if not runs:
			return None
		return (runs[-1].get('metadata') or {}).get('subExecution', {}).get('executionId')

	def get_execution(self, execution_id):
		"""Fetch one execution's full data by id, e.g. a child execution reached via get_child_execution_id."""
		params = {'includeData': 'true', 'redactExecutionData': 'false'}
		return self._request('get', f'{API_BASE}/executions/{execution_id}', params=params)

	def get_node_output(self, execution, node_name):
		"""Return node_name's latest-run first item json, or None if it never ran in this execution."""
		run_data = execution.get('data', {}).get('resultData', {}).get('runData', {})
		runs = run_data.get(node_name)
		if not runs:
			return None
		items = (runs[-1].get('data', {}).get('main') or [[]])[0] or []
		return items[0]['json'] if items else None

	def trigger_webhook(self, webhook_path, body):
		"""POST to the workflow's live webhook; it acks immediately and runs asynchronously."""
		return self._request('post', f'{WEBHOOK_BASE}/webhook/{webhook_path}', raise_for_status=False, json=body)

	def update_workflow(self, workflow_id, definition):
		"""Replace an existing (possibly active) workflow's content; n8n re-publishes it automatically."""
		return self._request('put', f'{API_BASE}/workflows/{workflow_id}', json=definition)

	def wait_for_execution(self, workflow_id, after_id=0, timeout=30, interval=1):
		"""Poll until a terminal execution newer than after_id appears — a plain "newest execution"
		check would race: it can return the PREVIOUS case's already-finished execution if that's
		still the newest record at the moment polling starts. Reusing one workflow across cases in
		a suite (see runner.run_suite) makes that race a near-certainty rather than an edge case."""
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			listing = self._request('get', f'{API_BASE}/executions', params={'workflowId': workflow_id, 'limit': 5})
			executions = listing.get('data') or []
			fresh = [item for item in executions if int(item['id']) > after_id and item['status'] in TERMINAL_STATUSES]
			if fresh:
				execution_id = min(fresh, key=lambda item: int(item['id']))['id']
				params = {'includeData': 'true', 'redactExecutionData': 'false'}
				return self._request('get', f'{API_BASE}/executions/{execution_id}', params=params)
			time.sleep(interval)
		raise TimeoutError(f'No finished execution for workflow {workflow_id} newer than {after_id} within {timeout}s')

	def _request(self, method, url, raise_for_status=True, **kwargs):
		response = requests.request(method, url, headers=self._headers, timeout=self._timeout, **kwargs)
		if raise_for_status:
			response.raise_for_status()
		return response.json() if response.content else None
