"""Thin wrapper around the n8n REST API used to run ephemeral, disposable workflow copies."""
import os
import time

import requests

# The public REST API only lives on the main process — n8n-main and n8n-webhook share the
# "n8n.blas.local" DNS alias on the docker network and round-robin between them, so hitting
# /api/v1 through that alias 404s roughly half the time. The container name is unambiguous.
API_BASE = 'http://da-sapot-n8n-main:5678/api/v1'
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

	def deactivate_workflow(self, workflow_id):
		"""Deactivate a workflow before deleting it."""
		self._request('post', f'{API_BASE}/workflows/{workflow_id}/deactivate')

	def delete_workflow(self, workflow_id, attempts=3, retry_delay=2):
		"""Permanently remove a (disposable, test-only) workflow, retrying on transient 5xx errors."""
		# A workflow with a still-settling recursive self-call chain (see path_queue) can 500 on
		# delete for a moment after its last execution finishes; a short retry clears it reliably.
		for attempt in range(attempts):
			try:
				self._request('delete', f'{API_BASE}/workflows/{workflow_id}')
				return
			except requests.HTTPError:
				if attempt == attempts - 1:
					raise
				time.sleep(retry_delay)

	def get_latest_execution_id(self, workflow_id):
		"""Snapshot the newest execution id for workflow_id, used as a baseline before triggering."""
		listing = self._request('get', f'{API_BASE}/executions', params={'workflowId': workflow_id, 'limit': 1})
		executions = listing.get('data') or []
		return int(executions[0]['id']) if executions else 0

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
