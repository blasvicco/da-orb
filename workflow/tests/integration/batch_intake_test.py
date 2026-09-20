"""Standalone integration test for the Batch Intake Agent.

Unlike cases/integration/*.json, this doesn't fit the generic runner: it needs two real
bucket files uploaded as a setup step, and it deliberately does NOT pin the Agent — the
whole point is validating its real extraction/reasoning quality against mixed-format
fixtures (see workflow/tests/mocks/), not just the deterministic wiring around it. Costs
one real OpenAI call per run.

Exercises the standalone "Batch Intake Agent (test harness) v1" workflow rather than the
live Orbot workflow's real /webhook/chat — Orbot's routing trunk now calls into this same
Agent for real (see batch_execution_test.py for the full end-to-end path including SAP
execution), but this harness lets the intake/extraction step alone be tested in isolation,
without paying for a real SAP MCP call per item.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/batch_intake_test.py
"""
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from engine.n8n_client import N8nClient  # noqa: E402

DJANGO_HOST = 'bvs.blas.local'
DATABASE = 'BVS_SA_NEW_16062025'
USERNAME = 'Evicco'
PASSWORD = 'Az21'
MOCKS_DIR = Path(__file__).parent.parent / 'mocks'
HARNESS_WORKFLOW_ID = 'KmfKdmJarmLcUbOG'
HARNESS_WEBHOOK_PATH = 'batch-intake-test'
RESULT_NODE = 'Batch Intake Result'
REQUIRED_LINE_FIELDS = {'ItemCode', 'Quantity', 'LineVendor', 'CostingCode', 'CostingCode2'}


def django_login():
	"""Real B1S login against the bvs org, matching this repo's standard test credentials."""
	response = requests.post(
		'http://localhost/api/v1/auth/login/',
		headers={'Host': DJANGO_HOST},
		json={'database': DATABASE, 'username': USERNAME, 'password': PASSWORD},
		timeout=15,
	)
	response.raise_for_status()
	return response.json()


def create_test_session():
	"""Seed a throwaway MChatSession directly — no REST endpoint creates one ad-hoc."""
	# Real sessions are only ever created lazily by the WS consumer's message_send.
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


def first_line(item):
	"""Each mock PR has exactly one line item entry — return it (or {})."""
	return (item.get('payload', {}).get('items') or [{}])[0]


def check_items(items):
	"""Return a list of failure strings; empty means the Agent's extraction looks correct."""
	failures = []
	if len(items) != 4:
		failures.append(f'expected 4 items, got {len(items)}')

	quantities = sorted(int(first_line(item).get('Quantity', -1)) for item in items)
	if quantities != [8, 15, 20, 50]:
		failures.append(f'expected quantities [8, 15, 20, 50] (one per source row), got {quantities}')

	# Marta López's row (Quantity 8) carries a deliberately nonexistent ItemCode
	# (NP-9999, unlike every other row's NP-0047) rather than a missing field —
	# this checks the Agent extracts it faithfully rather than "fixing"
	# suspicious-looking values on its own.
	bad_item = next((item for item in items if first_line(item).get('Quantity') == 8), None)
	if bad_item is None:
		failures.append('could not find the Quantity-8 row (Marta López) among extracted items')
	elif first_line(bad_item).get('ItemCode') != 'NP-9999':
		failures.append(f"expected Marta López's row to keep ItemCode 'NP-9999' verbatim, got {first_line(bad_item)}")

	missing_fields = [item for item in items if REQUIRED_LINE_FIELDS - set(first_line(item).keys())]
	if missing_fields:
		failures.append(f'expected every item to have all required line fields present, found gaps in {missing_fields}')

	return failures


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()

	csv_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitudes_compra.csv', 'text/csv')
	pdf_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitud_compra.pdf', 'application/pdf')

	payload = {
		'bucket_file_ids': [csv_id, pdf_id],
		'message': (
			'Por favor usa el contenido de estos 2 archivos para crear las solicitudes '
			'de compra requeridas.'
		),
		# Prompt: Batch Intake resolves each item's process-index path itself now (same
		# GitHub lookup Agent: Find does), so it needs the full organization dict —
		# specifically integration.target — not just the slug.
		'organization': {
			'id': 1,
			'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
			'name': 'BVS',
			'plan': {},
			'seat_limit': 25,
			'slug': 'bvs',
		},
		'session': {'access_token': access_token},
	}

	client = N8nClient()
	baseline_id = client.get_latest_execution_id(HARNESS_WORKFLOW_ID)
	client.trigger_webhook(HARNESS_WEBHOOK_PATH, payload)
	# Real tool calls (Read Bucket File -> extraction sub-workflow) plus the model's own
	# reasoning time regularly take 2-3 minutes end to end — this is not a wiring test.
	execution = client.wait_for_execution(HARNESS_WORKFLOW_ID, after_id=baseline_id, timeout=240)
	output = client.get_node_output(execution, RESULT_NODE)

	if output is None:
		print(f'not ok - node "{RESULT_NODE}" never ran (status={execution.get("status")})')
		sys.exit(1)

	# The Agent node's own json wraps the structured-parser result under "output".
	items = output.get('output', {}).get('items') or []
	failures = check_items(items)

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		print('\nfull items payload:')
		print(items)
		sys.exit(1)

	print('ok - Batch Intake Agent extracted 4 separate items from 2 mixed-format files (CSV + PDF), '
		  "preserving Marta López's invalid ItemCode verbatim rather than dropping or fixing it")


if __name__ == '__main__':
	main()
