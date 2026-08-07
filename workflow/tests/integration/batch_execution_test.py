"""Standalone integration test for the full batch EXECUTION loop (not just intake).

Exercises the real, live "Orbot v6" workflow's actual /webhook/chat webhook — not a
harness — since this is the real routing path (Agent: Find -> batch -> Agent: Batch
Intake -> Resolve Batch Item -> existing schema-fetch/execute_process pipeline ->
Handler: Completion/Error -> self-call for the next item -> ... -> final summary).

Real OpenAI calls, real SAP MCP calls (creates real Purchase Requests in the bvs test
company), real self-call recursion across multiple n8n executions. Costly and slow
(several minutes) by nature — this is not a wiring test.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/batch_execution_test.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from engine.n8n_client import N8nClient  # noqa: E402

DJANGO_HOST = 'bvs.blas.local'
DATABASE = 'BVS_SA_NEW_16062025'
USERNAME = 'Evicco'
PASSWORD = 'Az21'
MOCKS_DIR = Path(__file__).parent.parent / 'mocks'
ORBOT_WORKFLOW_ID = 'A4tWYpCiZA0EQgCE'
CHAT_WEBHOOK_PATH = 'chat'
SUMMARY_MARKERS = ('Ejecución por lotes completada', 'Batch execution completed')
API_BASE = 'http://da-sapot-n8n-main:5678/api/v1'


def django_login():
	response = requests.post(
		'http://localhost/api/v1/auth/login/',
		headers={'Host': DJANGO_HOST},
		json={'database': DATABASE, 'username': USERNAME, 'password': PASSWORD},
		timeout=15,
	)
	response.raise_for_status()
	return response.json()


def create_test_session():
	script = (
		"from drf_api.models import MChatSession, MOrganization\n"
		"org = MOrganization.objects.get(slug='bvs')\n"
		f"session = MChatSession.objects.create(connection_key='{DATABASE}', org=org, username='{USERNAME}')\n"
		"print(session.id)\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return int(result.stdout.strip().splitlines()[-1])


def upload_file(session_id, access_token, path, mime_type):
	with open(path, 'rb') as handle:
		response = requests.post(
			'http://localhost/api/v1/bucket/upload/',
			headers={'Host': DJANGO_HOST, 'Authorization': f'Bearer {access_token}'},
			data={'session_id': session_id},
			files={'file': (path.name, handle, mime_type)},
			timeout=15,
		)
	response.raise_for_status()
	return response.json()['id']


def find_summary_execution(headers, after_id, deadline):
	"""Poll every execution of the Orbot workflow newer than after_id until the terminal, summary-bearing one shows up."""
	# The self-call chain spans several separate executions, not one.
	seen_ids = set()
	while time.monotonic() < deadline:
		listing = requests.get(
			f'{API_BASE}/executions', headers=headers,
			params={'workflowId': ORBOT_WORKFLOW_ID, 'limit': 20}, timeout=15,
		).json()
		for item in listing.get('data') or []:
			execution_id = int(item['id'])
			if execution_id <= after_id or execution_id in seen_ids or item['status'] != 'success':
				continue
			seen_ids.add(execution_id)
			full = requests.get(
				f'{API_BASE}/executions/{execution_id}', headers=headers,
				params={'includeData': 'true', 'redactExecutionData': 'false'}, timeout=15,
			).json()
			run_data = full.get('data', {}).get('resultData', {}).get('runData', {})
			for node_name in ('Handle Batch Item Result', 'Normalize Response'):
				runs = run_data.get(node_name)
				if not runs:
					continue
				items = (runs[-1].get('data', {}).get('main') or [[]])[0] or []
				message = (items[0]['json'].get('message') or '') if items else ''
				if any(marker in message for marker in SUMMARY_MARKERS):
					return full, message
		time.sleep(5)
	raise TimeoutError('No batch summary execution found within the deadline')


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()

	csv_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitudes_compra.csv', 'text/csv')
	pdf_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitud_compra.pdf', 'application/pdf')

	payload = {
		'bucket_file_ids': [csv_id, pdf_id],
		'expertise_level': 2,
		'group_name': f'batch_execution_test_{session_id}',
		'message': (
			'Por favor usa el contenido de estos 2 archivos para crear las solicitudes '
			'de compra requeridas.'
		),
		'organization': {
			'id': 1,
			'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
			'name': 'BVS',
			'plan': {},
			'seat_limit': 25,
			'slug': 'bvs',
		},
		# Production traffic never needs this: Django's N8nClient swaps in the real
		# decrypted password server-side (via the access_token -> MSessionProxy
		# lookup) before firing to n8n. This test bypasses that WS/Django layer
		# entirely and posts straight to the webhook, so it has to supply the real
		# password itself, same as any other test in this repo using these creds.
		'session': {'access_token': access_token, 'database': DATABASE, 'user': {'password': PASSWORD, 'username': USERNAME}},
		'session_id': None,
	}

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}
	baseline_id = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)

	print('Triggered — polling for the batch summary (this can take several minutes)...')
	deadline = time.monotonic() + 600
	execution, message = find_summary_execution(headers, baseline_id, deadline)

	print('--- Summary message ---')
	print(message)

	run_data = execution.get('data', {}).get('resultData', {}).get('runData', {})
	items = (run_data['Normalize Response'][-1]['data']['main'][0]) or []
	intention_nodes = items[0]['json'].get('intention_nodes') or [] if items else []
	batch_nodes = [node for node in intention_nodes if node.get('batch_id')]

	failures = []
	if '4' not in message and len(batch_nodes) != 4:
		failures.append(
			f'expected 4 batch nodes, found {len(batch_nodes)}: '
			f'{[node.get("status") for node in batch_nodes]}'
		)
	statuses = sorted(node.get('status') for node in batch_nodes)
	# 3 of the 4 mock rows use known-good SAP master data and are expected to succeed.
	# Marta López's row (mocks/solicitudes_compra.csv) uses a deliberately nonexistent
	# ItemCode (NP-9999) so SAP genuinely rejects it — this proves the self-call chain
	# continues correctly past a real per-item failure instead of stalling the batch.
	if statuses.count('completed') != 3 or statuses.count('failed') != 1:
		failures.append(f'expected 3 completed + 1 failed, got {statuses}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - batch execution processed all 4 items sequentially (3 completed, 1 failed), '
		  f'session_id={session_id}')


if __name__ == '__main__':
	main()
