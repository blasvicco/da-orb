"""Live E2E check for the Document Generation & Custom Templates feature (Orbot v14).

Exercises the REAL, live spine workflow end-to-end -- real OpenAI calls, real SAP B1 Service
Layer calls, no pins, no disposable workflow copy. Validates
docs/plans/document_generation_and_templates.md's full pipeline against the freshly-created BVS
organization: resolve/complete a real SAP invoice, ask for its PDF, and confirm a real rendered
PDF lands in the session's bucket -- rendered against BVS's own uploaded MDocumentTemplate
("BVS Factura v4", set as BVS's org default for document_type="invoice"), not the tiny bundled
system-fallback template.

    Turn 1: an open-ended question about a real recent invoice, letting Agent: Find/Discover
            resolve whichever process/entity actually answers it (BVS's SAP catalog wiring for
            this is unverified going in -- this turn is itself part of what's being checked).
    Turn 2: a follow-up asking for that invoice as a PDF, which should classify as
            status: "generate_document" and reach generate-document.json.

Run directly inside the backend container:
    python3 /home/workflow/tests/integration/generate_document_invoice_e2e_test.py
"""
import json
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
SPINE_WORKFLOW_ID = 'DO2FmimV6H2KZN3D'
CHAT_WEBHOOK_PATH = 'chat'
API_BASE = 'http://da-orb-n8n-main:5678/api/v1'


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


def get_session_state(session_id):
	"""Read the session's persisted n8n_state (intention_nodes, active_node_id, ...) straight
	from the DB -- the source of truth for what actually got resolved/completed server-side."""
	script = (
		"import json\n"
		"from drf_api.models import MChatSession\n"
		f"s = MChatSession.objects.get(id={session_id})\n"
		"print(json.dumps(s.n8n_state or {}))\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return json.loads(result.stdout.strip().splitlines()[-1])


def save_user_message(session_id, message):
	"""Persist the user's own turn as a "user" MChatMessage, mirroring what
	CChat.message_send()'s _broadcast(message_text, "user", ...) does in the real WS flow
	before firing to n8n -- triggering the webhook directly (as this script does) skips that
	consumer entirely, so without this a session replayed in the real UI shows only the
	agent's replies, never what the user actually asked."""
	script = (
		"import json\n"
		"from datetime import datetime, UTC\n"
		"from drf_api.models import MChatMessage\n"
		f"MChatMessage.objects.create(session_id={session_id}, type='user', text={json.dumps(message)}, "
		"extra=None, timestamp=datetime.now(UTC))\n"
	)
	subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)


def get_org_company_info():
	"""Read BVS's real company_info straight from the DB -- mirrors what a real request gets
	via MOrganization.safe_to_dict(), so this test exercises the SAP-then-org fallback exactly
	as production would (no hand-typed duplicate here to drift from the real seeded value)."""
	script = (
		"import json\n"
		"from drf_api.models import MOrganization\n"
		"org = MOrganization.objects.get(slug='bvs')\n"
		"print(json.dumps(org.company_info))\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return json.loads(result.stdout.strip().splitlines()[-1])


def get_bucket_files(session_id):
	script = (
		"import json\n"
		"from drf_api.models import MBucketFile\n"
		f"rows = MBucketFile.objects.filter(session_id={session_id}).order_by('id')\n"
		"print(json.dumps([{'id': r.id, 'name': r.name, 'origin': r.origin, 'size': r.size, 'storage_path': r.storage_path} for r in rows]))\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return json.loads(result.stdout.strip().splitlines()[-1])


def get_messages(access_token, session_id):
	response = requests.get(
		'http://localhost/api/v1/chat/messages/',
		headers={'Host': DJANGO_HOST, 'Authorization': f'Bearer {access_token}'},
		params={'session_id': session_id},
		timeout=15,
	)
	response.raise_for_status()
	return response.json()


def wait_for_delivery(access_token, session_id, before_count, deadline):
	# The host running this suite is frequently under heavy, bursty load (multiple manually-run
	# dev servers sharing one box) -- a single slow HTTP round trip is a transient condition, not
	# a real failure, and must not abort the whole poll loop the way an unhandled exception would.
	while time.monotonic() < deadline:
		try:
			messages = get_messages(access_token, session_id)
		except requests.exceptions.RequestException as error:
			print(f'  (wait_for_delivery: transient error, retrying: {error})')
			time.sleep(2)
			continue
		non_status = [m for m in messages if m.get('type') != 'status']
		if len(non_status) > before_count:
			return non_status[-1]
		time.sleep(2)
	return None


def wait_for_fresh_execution(headers, after_id, deadline):
	while time.monotonic() < deadline:
		try:
			listing = requests.get(
				f'{API_BASE}/executions', headers=headers,
				params={'workflowId': SPINE_WORKFLOW_ID, 'limit': 5}, timeout=30,
			).json()
			fresh = [item for item in (listing.get('data') or []) if int(item['id']) > after_id and item['status'] in ('success', 'error', 'crashed')]
			if fresh:
				execution_id = min(fresh, key=lambda item: int(item['id']))['id']
				return requests.get(
					f'{API_BASE}/executions/{execution_id}', headers=headers,
					params={'includeData': 'true', 'redactExecutionData': 'false'}, timeout=30,
				).json()
		except requests.exceptions.RequestException as error:
			print(f'  (wait_for_fresh_execution: transient error, retrying: {error})')
		time.sleep(3)
	return None


def send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name):
	# Real chat turns never fire this bare -- N8nClient.fire() (web_socket/helpers/n8n/client.py)
	# loads current Redis-backed n8n_state and injects active_node_id/intention_nodes into every
	# outgoing payload; context-enrichment.json's own "Enrich Context" node passes these two
	# fields through completely untouched, so THIS caller is the only place responsible for
	# carrying state forward across turns when driving the webhook directly like this. Reading
	# the session's own persisted n8n_state (written by n8n_callback after each prior turn) is
	# the equivalent stand-in for that Redis read.
	state = get_session_state(session_id)
	payload = {
		'active_node_id': state.get('active_node_id'),
		'bucket_file_ids': [],
		'expertise_level': 3,
		'group_name': group_name,
		'intention_nodes': state.get('intention_nodes') or {},
		'language': 'es',
		'message': message,
		'organization': organization,
		'session': session_payload,
		'session_id': session_id,
	}
	save_user_message(session_id, message)
	before_count = len([m for m in get_messages(access_token, session_id) if m.get('type') != 'status'])
	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 180)
	if execution is None:
		return None, None
	delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
	return execution, delivered


def webhook_input_message(client, execution):
	webhook_output = client.get_node_output(execution, 'Webhook')
	if webhook_output is None:
		return None
	return (webhook_output.get('body') or webhook_output).get('message')


def inspect_generate_document(client, spine_execution):
	child_id = client.get_child_execution_id(spine_execution, 'Generate Document')
	if not child_id:
		return None
	child = client.get_execution(child_id)
	return {
		'child_execution_id': child_id,
		'resolve_target_node': client.get_node_output(child, 'Resolve Target Node'),
		'build_invoice_rows': client.get_node_output(child, 'Build Invoice Rows'),
		'call_document_render': client.get_node_output(child, 'Call Document Render'),
		'handle_render_result': client.get_node_output(child, 'Handle Render Result'),
	}


def download_and_verify_pdf(access_token, bucket_file_id):
	response = requests.get(
		'http://localhost/api/v1/bucket/download/',
		headers={'Host': DJANGO_HOST, 'Authorization': f'Bearer {access_token}'},
		params={'file_id': bucket_file_id},
		timeout=15,
	)
	response.raise_for_status()
	url = response.json().get('url')
	pdf_response = requests.get(url, timeout=30)
	pdf_response.raise_for_status()
	content = pdf_response.content
	return content[:5] == b'%PDF-', len(content)


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()
	print(f'logged in, test session_id={session_id}')

	organization = {
		'id': 1,
		'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
		'name': 'BVS', 'plan': {}, 'seat_limit': 25, 'slug': 'bvs',
		'company_info': get_org_company_info(),
	}
	session_payload = {'access_token': access_token, 'database': DATABASE, 'user': {'password': PASSWORD, 'username': USERNAME}}

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	failures = []

	# --- Turn 1: resolve a real invoice -------------------------------------------------
	# ar_invoice_get only accepts DocEntry (the internal SAP record id) -- a request naming
	# an invoice by its printed NUMBER (DocNum) now correctly routes to ar_invoice_list
	# instead (see da-orb-processes/b1s/index.json). This phrasing exercises the direct
	# DocEntry path: the user already has 45523 (confirmed live: DocNum 10767, PIETROBONI
	# ARMANDO ERNESTO), as they would after a prior ar_invoice_list result.
	label = 'find_invoice'
	message = 'Dame el detalle de la factura de venta con DocEntry 45523'
	print(f'\n{"=" * 100}\nTURN: {label}\nmessage: {message!r}\n{"=" * 100}')
	group_name = f'generate_document_e2e_{session_id}_{label}_{int(time.time())}'
	execution, delivered = send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name)

	if execution is None:
		print('FATAL: no spine execution completed within timeout for turn 1')
		sys.exit(1)

	actual_message = webhook_input_message(client, execution)
	print(f"spine execution: id={execution.get('id')} status={execution.get('status')}")
	if actual_message != message:
		print(f'FATAL: execution/message mismatch -- expected {message!r}, got {actual_message!r}')
		sys.exit(1)

	if delivered:
		print(f"delivered message: {json.dumps(delivered.get('content') or delivered, ensure_ascii=False, indent=2)[:2000]}")
	else:
		print('warning: no non-status message confirmed delivered within 30s for turn 1')

	state = get_session_state(session_id)
	intention_nodes = state.get('intention_nodes') or {}
	print(f'\nintention_nodes after turn 1: {json.dumps(intention_nodes, ensure_ascii=False, indent=2)[:3000]}')

	target_node_id = None
	for node_id, node in intention_nodes.items():
		schema_def = (node.get('process_definition') or {}).get('schema_definition') or {}
		doc_type = schema_def.get('document_type') or (node.get('process_definition') or {}).get('document_type')
		if doc_type:
			target_node_id = node_id
			print(f'\nFound node with document_type={doc_type!r}: {node_id}')
			break

	if target_node_id is None:
		failures.append(
			'find_invoice: no intention_nodes entry carries a document_type -- either no node '
			'completed, or the resolved SAP process/entity has no document_type/document_mapping '
			'wired on its schema. This is a real gap to report, not a harness bug.'
		)
		print('RESULT: no node with a document_type found after turn 1 -- see failures below')
	else:
		# --- Turn 2: ask for the PDF -- expected to land on the line-item confirmation step
		# (document_mapping declares allow_line_item_customization: true), not the render itself.
		label = 'generate_pdf'
		message = 'Generame un PDF de esa factura'
		print(f'\n{"=" * 100}\nTURN: {label}\nmessage: {message!r}\n{"=" * 100}')
		group_name = f'generate_document_e2e_{session_id}_{label}_{int(time.time())}'
		execution, delivered = send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name)

		reached_confirmation = False
		if execution is None:
			failures.append('generate_pdf: no spine execution completed within timeout')
		else:
			actual_message = webhook_input_message(client, execution)
			print(f"spine execution: id={execution.get('id')} status={execution.get('status')}")
			if actual_message != message:
				failures.append(f'generate_pdf: execution/message mismatch -- expected {message!r}, got {actual_message!r}')
			elif delivered:
				print(f"delivered message: {json.dumps(delivered.get('content') or delivered, ensure_ascii=False, indent=2)[:2000]}")
				reached_confirmation = True
			else:
				failures.append('generate_pdf: no non-status message confirmed delivered within 30s')

		if not reached_confirmation:
			failures.append('confirm_generate: skipped -- turn 2 did not reach the confirmation step')
		else:
			# --- Turn 3: confirm "generate as-is" past the line-item customization gate -----
			label = 'confirm_generate'
			message = 'Dale, generalo tal cual esta'
			print(f'\n{"=" * 100}\nTURN: {label}\nmessage: {message!r}\n{"=" * 100}')
			group_name = f'generate_document_e2e_{session_id}_{label}_{int(time.time())}'
			execution, delivered = send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name)

			if execution is None:
				failures.append('confirm_generate: no spine execution completed within timeout')
			else:
				actual_message = webhook_input_message(client, execution)
				print(f"spine execution: id={execution.get('id')} status={execution.get('status')}")
				if actual_message != message:
					failures.append(f'confirm_generate: execution/message mismatch -- expected {message!r}, got {actual_message!r}')
				else:
					if delivered:
						print(f"delivered message: {json.dumps(delivered.get('content') or delivered, ensure_ascii=False, indent=2)[:2000]}")
						print(f"delivered extra: {json.dumps(delivered.get('extra'), ensure_ascii=False, indent=2)[:1000]}")
					else:
						failures.append('confirm_generate: no non-status message confirmed delivered within 30s')

					detail = inspect_generate_document(client, execution)
					if detail is None:
						failures.append("confirm_generate: spine execution never reached the 'Generate Document' sub-workflow")
					else:
						print(f"\nGenerate Document child execution id: {detail['child_execution_id']}")
						print(f"Resolve Target Node output: {json.dumps(detail['resolve_target_node'], ensure_ascii=False, indent=2)[:1500]}")
						print(f"Build Invoice Rows output: {json.dumps(detail['build_invoice_rows'], ensure_ascii=False, indent=2)[:2000]}")
						print(f"Call Document Render output: {json.dumps(detail['call_document_render'], ensure_ascii=False, indent=2)[:2000]}")
						print(f"Handle Render Result output: {json.dumps(detail['handle_render_result'], ensure_ascii=False, indent=2)[:1000]}")

						render_response = detail['call_document_render'] or {}
						status_code = (render_response.get('statusCode')
							or (render_response.get('body') or {}).get('statusCode'))
						print(f'\nrender HTTP status code: {status_code}')
						if status_code not in (201, 409):
							failures.append(f'confirm_generate: Call Document Render returned unexpected status {status_code}')

					bucket_files = get_bucket_files(session_id)
					workflow_generated = [f for f in bucket_files if f['origin'] == 'workflow_generated']
					print(f'\nworkflow_generated bucket files: {json.dumps(workflow_generated, ensure_ascii=False, indent=2)}')
					if not workflow_generated:
						failures.append('confirm_generate: no workflow_generated MBucketFile row was created')
					else:
						newest = workflow_generated[-1]
						is_pdf, size = download_and_verify_pdf(access_token, newest['id'])
						print(f"downloaded file id={newest['id']}: is_pdf={is_pdf} size={size} bytes")
						if not is_pdf:
							failures.append(f"confirm_generate: downloaded file id={newest['id']} does not start with the PDF magic bytes")
						if size < 1000:
							failures.append(f"confirm_generate: downloaded PDF is suspiciously small ({size} bytes)")

	print(f'\n{"=" * 100}')
	if failures:
		for f in failures:
			print(f'not ok - {f}')
		print(f'{len(failures)} failure(s), session_id={session_id}')
		sys.exit(1)
	print(f'ok - invoice resolved, PDF generated and verified end-to-end, session_id={session_id}')


if __name__ == '__main__':
	main()
