"""Live E2E for UC-3 (docs/use_cases/03_file_upload_batch_creation.md): upload the two mock
files (CSV + PDF, workflow/tests/mocks/) and drive them through the REAL Orbot spine
(gl7Ax8b77WhVUTmw, /webhook/chat) end to end -- extraction, classification, batch record
splitting, and real SAP creation. No pins: this is deliberately the full real path, costing
real OpenAI + SAP calls, to catch exactly the class of bug fixed on 2026-08-16 (see UC-3's
"Notable gaps") that pinned/unit tests can't: an LLM merging distinct CSV rows into one
record, or the extraction pipeline silently dropping a file.

Fixture files have an explicit fecha_documento/"Fecha del Documento" (2026-08-14, a Friday)
so DocDate doesn't fall through to SAP's own today-default -- the SAP sandbox has no exchange
rate for USD on weekends, which would otherwise fail every create for an unrelated reason.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/file_upload_batch_creation_test.py
"""
import json
import subprocess
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from engine.n8n_client import N8nClient  # noqa: E402

DJANGO_HOST = 'bvs.blas.local'
DATABASE = 'BVS_SA_NEW_16062025'
USERNAME = 'Evicco'
PASSWORD = 'Az21'
MOCKS_DIR = Path(__file__).parent.parent / 'mocks'
SPINE_WORKFLOW_ID = 'gl7Ax8b77WhVUTmw'
WEBHOOK_PATH = 'chat'
MESSAGE = 'crea solicitudes de compra con el contenido de estos archivos'


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
	"""Seed a throwaway MChatSession directly -- no REST endpoint creates one ad-hoc."""
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


def fetch_messages(session_id, access_token):
	response = requests.get(
		'http://localhost/api/v1/chat/messages/',
		headers={'Host': DJANGO_HOST, 'Authorization': f'Bearer {access_token}'},
		params={'session_id': session_id},
		timeout=15,
	)
	response.raise_for_status()
	return response.json()


def fetch_n8n_state(session_id):
	"""SChatMessage (the /messages/ REST response) has no state field -- the exported chat
	JSON the frontend produces merges it in client-side from a separate source. The actual
	source of truth Django persists to is MChatSession.n8n_state (see
	_resolve_and_persist_state in drf_api/resources/chat/main.py) -- read it directly."""
	script = (
		"import json\n"
		"from drf_api.models import MChatSession\n"
		f"session = MChatSession.objects.get(id={session_id})\n"
		"print(json.dumps(session.n8n_state))\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return json.loads(result.stdout.strip().splitlines()[-1])


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()

	csv_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitudes_compra.csv', 'text/csv')
	pdf_id = upload_file(session_id, access_token, MOCKS_DIR / 'solicitud_compra.pdf', 'application/pdf')
	print(f'uploaded bucket_file_ids: csv={csv_id}, pdf={pdf_id}')

	payload = {
		'active_node_id': None,
		'bucket_file_ids': [csv_id, pdf_id],
		'expertise_level': 3,
		'group_name': f'chat_1_{USERNAME}_{uuid.uuid4().hex}',
		'intention_nodes': {},
		'message': MESSAGE,
		'organization': {
			'id': 1,
			'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
			'name': 'BVS',
			'plan': {},
			'seat_limit': 25,
			'slug': 'bvs',
		},
		# django_login()'s raw response only carries an opaque proxy access_token --
		# the real database/username/password only get substituted in server-side by
		# N8nClient._resolve_session_payload() (see app/backend/web_socket/helpers/
		# n8n/client.py), which we bypass entirely by hitting the webhook directly.
		# Reproduce that substitution here with the same known test credentials.
		'session': {
			**session_data,
			'database': DATABASE,
			'user': {'password': PASSWORD, 'username': USERNAME},
		},
		'session_id': session_id,
	}

	client = N8nClient()
	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(WEBHOOK_PATH, payload)
	print('webhook triggered, waiting for the spine execution to finish '
		  '(file extraction + 2 LLM calls + up to 4 real SAP creates -- can take 2-3 minutes)...')
	client.wait_for_execution(SPINE_WORKFLOW_ID, after_id=baseline_id, timeout=300)

	messages = fetch_messages(session_id, access_token)
	agent_messages = [m for m in messages if m.get('type') == 'agent']
	if not agent_messages:
		print(f'not ok - no agent message was ever delivered for session {session_id}')
		sys.exit(1)

	final = agent_messages[-1]
	print(f'\ndelivered message:\n{final.get("text")}\n')

	nodes = fetch_n8n_state(session_id).get('intention_nodes') or {}
	statuses = {node_id: node.get('status') for node_id, node in nodes.items()}
	completed = sum(1 for s in statuses.values() if s == 'completed')
	failed = sum(1 for s in statuses.values() if s == 'failed')
	print(f'intention_nodes: {len(nodes)} total, {completed} completed, {failed} failed')
	for node_id, node in nodes.items():
		line_summary = [item.get('ItemCode') for item in (node.get('form_state', {}).get('items') or [])]
		print(f'  {node_id}: status={node.get("status")} items={line_summary}')

	if len(nodes) != 4:
		print(f'not ok - expected 4 intention_nodes (one per source record), got {len(nodes)}')
		sys.exit(1)
	if completed != 3:
		print(f'not ok - expected 3 completed, got {completed} (see per-node breakdown above)')
		sys.exit(1)

	print('\nok - 4 records extracted, 3 Purchase Requests created successfully')


if __name__ == '__main__':
	main()
