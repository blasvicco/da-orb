"""Standalone integration test for the expertise_level===1 batch CONFIRMATION GATE.

Exercises the real, live "Orbot" workflow's actual /webhook/chat webhook — not a harness —
in two phases:
  1. Send the batch-triggering message at expertise_level:1 and confirm the workflow asks
     "¿Confirmas...?" and stops (a real round trip through Django's n8n_callback, not a
     same-execution self-call — see Gate: Batch Confirmation / upload_and_file_bucket.md).
  2. Send a second, real webhook call with an affirmative reply ("sí") — carrying the
     awaiting_batch_confirmation/pending_batch_items fields this test extracts from phase 1,
     mirroring exactly what Django's real N8nClient.fire() would send from persisted Redis
     state (this script bypasses the WS/Django-fire layer, same as batch_execution_test.py,
     so it has to reconstruct that payload itself) — and confirm the batch then actually
     executes and completes, same outcome as batch_execution_test.py's expertise_level:2 case.

Real OpenAI calls, real SAP MCP calls (creates real Purchase Requests in the bvs test
company), real self-call recursion across multiple n8n executions. Costly and slow (several
minutes) by nature — this is not a wiring test.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/batch_confirmation_test.py
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
CONFIRMATION_MARKERS = ('¿Confirmas', 'Do you want me to create')
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


def find_execution_with_message_marker(headers, after_id, deadline, markers, node_names=('Normalize Response',)):
	"""Poll every execution of the Orbot workflow newer than after_id until a named node's output message matches."""
	# Returns (execution, message, node_json) for the matching node.
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
			for node_name in node_names:
				runs = run_data.get(node_name)
				if not runs:
					continue
				items = (runs[-1].get('data', {}).get('main') or [[]])[0] or []
				if not items:
					continue
				node_json = items[0]['json']
				message = node_json.get('message') or ''
				if any(marker in message for marker in markers):
					return full, message, node_json
		time.sleep(5)
	raise TimeoutError('No execution matching the given markers found within the deadline')


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()

	csv_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitudes_compra.csv', 'text/csv')
	pdf_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitud_compra.pdf', 'application/pdf')

	organization = {
		'id': 1,
		'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
		'name': 'BVS',
		'plan': {},
		'seat_limit': 25,
		'slug': 'bvs',
	}
	session_payload = {'access_token': access_token, 'database': DATABASE, 'user': {'password': PASSWORD, 'username': USERNAME}}
	group_name = f'batch_confirmation_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	# --- Phase 1: trigger the batch at expertise_level 1, expect a confirmation ask ---
	baseline_id = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, {
		'bucket_file_ids': [csv_id, pdf_id],
		'expertise_level': 1,
		'group_name': group_name,
		'message': (
			'Por favor usa el contenido de estos 2 archivos para crear las solicitudes '
			'de compra requeridas.'
		),
		'organization': organization,
		'session': session_payload,
		'session_id': None,
	})

	print('Phase 1 triggered — polling for the confirmation ask (this can take a couple minutes)...')
	deadline_1 = time.monotonic() + 300
	confirmation_execution, confirmation_message, confirmation_json = find_execution_with_message_marker(
		headers, baseline_id, deadline_1, CONFIRMATION_MARKERS,
	)
	print('--- Confirmation message ---')
	print(confirmation_message)

	pending_batch_items = confirmation_json.get('pending_batch_items') or []
	failures = []
	if not confirmation_json.get('awaiting_batch_confirmation'):
		failures.append('expected awaiting_batch_confirmation=true on the confirmation-ask execution')
	if len(pending_batch_items) != 4:
		failures.append(f'expected 4 pending_batch_items, found {len(pending_batch_items)}')
	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	# --- Phase 2: reply affirmatively, expect the batch to actually execute ---
	baseline_id_2 = int(confirmation_execution['id'])
	client.trigger_webhook(CHAT_WEBHOOK_PATH, {
		# Mirrors what Django's real N8nClient.fire() would send from the state its
		# n8n_callback just persisted for real in phase 1 — this script bypasses that
		# WS/Django-fire layer (same as batch_execution_test.py), so it reconstructs
		# the payload directly from phase 1's own execution data instead.
		'awaiting_batch_confirmation': True,
		'expertise_level': 1,
		'group_name': group_name,
		'message': 'sí',
		'organization': organization,
		'pending_batch_items': pending_batch_items,
		'session': session_payload,
		'session_id': None,
	})

	print('Phase 2 triggered — polling for the batch summary (this can take several minutes)...')
	deadline_2 = time.monotonic() + 600
	summary_execution, summary_message, summary_json = find_execution_with_message_marker(
		headers, baseline_id_2, deadline_2, SUMMARY_MARKERS,
	)
	print('--- Summary message ---')
	print(summary_message)

	intention_nodes = summary_json.get('intention_nodes') or []
	batch_nodes = [node for node in intention_nodes if node.get('batch_id')]

	failures = []
	if '4' not in summary_message and len(batch_nodes) != 4:
		failures.append(
			f'expected 4 batch nodes, found {len(batch_nodes)}: '
			f'{[node.get("status") for node in batch_nodes]}'
		)
	statuses = sorted(node.get('status') for node in batch_nodes)
	# Same fixtures/expectation as batch_execution_test.py: 3 known-good rows succeed,
	# Marta López's row (deliberately nonexistent ItemCode) is rejected by SAP.
	if statuses.count('completed') != 3 or statuses.count('failed') != 1:
		failures.append(f'expected 3 completed + 1 failed, got {statuses}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print('ok - expertise_level:1 batch confirmation gate asked, then executed all 4 items '
		  f'after an affirmative reply (3 completed, 1 failed), session_id={session_id}')


if __name__ == '__main__':
	main()
