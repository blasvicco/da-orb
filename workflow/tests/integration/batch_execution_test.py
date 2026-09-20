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
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from engine.n8n_client import N8nClient  # noqa: E402


def most_recent_business_day():
	"""The bvs test company's USD exchange rate is only entered on business days — SAP B1
	rejects PurchaseRequest creation for a DocDate with no matching rate ("Update the
	exchange rate, 'USD'"), and that includes Saturdays and Sundays, not just "today" when
	today happens to be stale. This is test-data staleness, not a workflow bug: production
	DocDate should keep defaulting to "today" per the process schema.
	"""
	d = datetime.now() - timedelta(days=1)
	while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
		d -= timedelta(days=1)
	return d.strftime('%Y-%m-%d')


MOST_RECENT_BUSINESS_DAY = most_recent_business_day()

DJANGO_HOST = 'bvs.blas.local'
DATABASE = 'BVS_SA_NEW_16062025'
USERNAME = 'Evicco'
PASSWORD = 'Az21'
MOCKS_DIR = Path(__file__).parent.parent / 'mocks'
ORBOT_WORKFLOW_ID = 'A4tWYpCiZA0EQgCE'
CHAT_WEBHOOK_PATH = 'chat'
SUMMARY_MARKERS = ('Ejecución por lotes completada', 'Batch execution completed')
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
			# Handle Batch Item Result now lives inside the Batch sub-workflow (batch.json), so it
			# never appears in the spine's own runData directly -- only Execute Workflow: Output &
			# Delivery's embedded output is checkable here. Uses node_output() (defined below) for
			# its first-non-empty-branch logic, not a hardcoded main[0]: that terminal is commonly
			# a 2-output IF node (Has Pending Queue?) whose "done" case lands on branch 1, not 0.
			result = node_output(full, 'Execute Workflow: Output & Delivery') or {}
			message = result.get('message') or ''
			if any(marker in message for marker in SUMMARY_MARKERS):
				return full, message
		time.sleep(5)
	raise TimeoutError('No batch summary execution found within the deadline')


def wait_for_single_execution(headers, after_id, deadline):
	"""Poll until the very next terminal execution newer than after_id appears (single webhook turn, not a chain)."""
	while time.monotonic() < deadline:
		listing = requests.get(
			f'{API_BASE}/executions', headers=headers,
			params={'workflowId': ORBOT_WORKFLOW_ID, 'limit': 5}, timeout=15,
		).json()
		fresh = [item for item in (listing.get('data') or []) if int(item['id']) > after_id and item['status'] == 'success']
		if fresh:
			execution_id = min(fresh, key=lambda item: int(item['id']))['id']
			return requests.get(
				f'{API_BASE}/executions/{execution_id}', headers=headers,
				params={'includeData': 'true', 'redactExecutionData': 'false'}, timeout=15,
			).json()
		time.sleep(3)
	raise TimeoutError(f'No execution found newer than {after_id} within the deadline')


def node_output(execution, node_name):
	"""Return node_name's latest-run first item json for a single execution, or None if it never ran.
	Picks the first non-empty main branch rather than assuming index 0 — an Execute Workflow
	node's embedded inline output mirrors whichever branch its sub-workflow's own last-reached
	node actually fired (e.g. Output & Delivery's Has Pending Queue? is a 2-output IF node, and
	the common "no continuation" case lands on its false branch, index 1, not 0)."""
	run_data = execution.get('data', {}).get('resultData', {}).get('runData', {})
	runs = run_data.get(node_name)
	if not runs:
		return None
	branches = runs[-1].get('data', {}).get('main') or []
	items = next((branch for branch in branches if branch), [])
	return items[0]['json'] if items else None


def test_retry_after_failure(client, headers, base_payload, failed_node):
	"""Simulates the exact conversational flow this session's fixes targeted: the user
	clicks the failed batch node, asks what went wrong (intention_query), then supplies
	the missing field. Verifies the retry re-parents under the failed node and resumes
	with its already-collected Supplier/Comments/items instead of starting blank — the
	regression this session fixed in Register Intention Node. Real OpenAI classification,
	real webhook turns; no pins.
	"""
	failed_id = failed_node['id']
	original_form_state = failed_node.get('form_state') or {}
	print(f'\n=== Retry-after-failure: node {failed_id} ===')

	turn_a = {
		**base_payload,
		'message': 'me podés mostrar el error de esta solicitud de compra',
		'active_node_override': failed_id,
		'session_id': None,
	}
	baseline_a = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_a)
	exec_a = wait_for_single_execution(headers, baseline_a, time.monotonic() + 240)

	hiq = node_output(exec_a, 'Handler: Intention Query')
	if not hiq:
		print('not ok - Handler: Intention Query did not run for the informational question about the failed node')
		return False
	print('Turn A (intention_query) message:', hiq.get('message'))
	if not failed_node.get('error_detail') or failed_node['error_detail'] not in (hiq.get('message') or ''):
		print('not ok - the intention_query response did not surface the stored error_detail verbatim')
		return False

	# Turn B carries forward parent_override_id/intention_nodes exactly as Normalize
	# Response left them after turn A — this test posts straight to the webhook, bypassing
	# the Django/WS layer that would normally persist that state between turns for us.
	na = node_output(exec_a, 'Execute Workflow: Output & Delivery') or {}
	turn_b = {
		**base_payload,
		'message': 'la fecha requerida es el 2026-08-20',
		'parent_override_id': na.get('parent_override_id'),
		'intention_nodes': na.get('intention_nodes'),
		'session_id': None,
	}
	baseline_b = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_b)
	exec_b = wait_for_single_execution(headers, baseline_b, time.monotonic() + 240)

	print('Turn B (correction) Agent: Find output:', node_output(exec_b, 'Agent: Find'))
	decode_out = node_output(exec_b, 'Register Intention Node')
	if not decode_out:
		print('not ok - Register Intention Node did not run — the correction was never matched as a retry of the same process')
		return False

	new_node = next((n for n in (decode_out.get('intention_nodes') or []) if n.get('parent_id') == failed_id), None)
	if not new_node:
		print('not ok - no new node was parented under the failed node')
		return False

	# Supplier/Comments/items must be inherited *before* Agent: Form ever runs — check
	# Register Intention Node's own output for those (this is exactly what this session's
	# form_state-inheritance fix targets). RequriedDate is a different matter: whether
	# the correction message actually overwrites it is decided *by* Agent: Form, further
	# downstream in this same execution — so that specific check needs the turn's final,
	# post-Agent:Form state (Normalize Response), not this early snapshot.
	inherited = new_node.get('form_state') or {}
	ok = True
	for key in ('Supplier', 'Comments', 'items'):
		if inherited.get(key) != original_form_state.get(key):
			print(f'not ok - inherited form_state.{key} does not match the original request: '
				  f'{inherited.get(key)!r} != {original_form_state.get(key)!r}')
			ok = False

	nr = node_output(exec_b, 'Execute Workflow: Output & Delivery') or {}
	final_form_state = nr.get('form_state') or {}
	if final_form_state.get('RequriedDate') == original_form_state.get('RequriedDate'):
		print(f'not ok - RequriedDate was not updated with the correction by the end of the turn '
			  f'(still {final_form_state.get("RequriedDate")!r}); Normalize Response message: {nr.get("message")!r}')
		ok = False
	elif ok:
		print(f'ok - retry correctly re-parented under {failed_id}, inherited Supplier/Comments/items, '
			  f'and the correction updated RequriedDate to {final_form_state.get("RequriedDate")!r}')

	# Report (don't assert) the actual SAP resubmission outcome separately: this row may
	# still fail for a second, unrelated reason (its ItemCode may not exist in SAP) even
	# once the date is fixed — that's a genuine, separate finding, not a job for this
	# session's fixes, which are about the conversational mechanism, not this row's data.
	print(f'Turn B final state: node status={new_node.get("status")!r}, message={nr.get("message")!r}')

	return ok


def test_manual_retry_succeeds(client, headers, base_payload):
	"""Full happy-path retry: a node that failed *only* because RequriedDate was missing
	(all other fields already valid, known-good SAP master data) gets loaded, corrected,
	and resubmitted — and this time must actually succeed in SAP (status: completed, a
	real DocNum), not merely retain the corrected field. Unlike the batch's Marta López
	row (mocks/solicitudes_compra.csv), which uses a deliberately nonexistent ItemCode
	and can never succeed no matter what's corrected, everything here is known-good except
	the one field under test, so a genuine SAP success is the only passing outcome.
	"""
	failed_id = 'e2e_manual_retry#0'
	original_form_state = {
		'Supplier': 'C30715652664',
		'Comments': 'E2E manual retry test — missing RequriedDate on purpose.',
		'DocDate': MOST_RECENT_BUSINESS_DAY,
		'items': [{
			'ItemCode': 'NP-0047', 'Quantity': 3, 'LineVendor': 'P30679718378',
			'TaxCode': 'IVA_21', 'CostingCode': 'SupplyC', 'CostingCode2': 'ShareSer',
		}],
		'ready': False,
	}
	failed_node = {
		'id': failed_id, 'parent_id': None, 'process_id': 1,
		'process_definition': {'id': 1, 'name': 'Create Purchase Request'},
		'form_state': original_form_state, 'status': 'failed',
		'error_detail': "El servidor SAP devolvió: 'Required date is missing'. Falta el campo Required Date.",
	}
	print(f'\n=== Manual-retry-succeeds: node {failed_id} ===')

	turn_a = {
		**base_payload,
		'message': 'me podés mostrar el error de esta solicitud de compra',
		'active_node_override': failed_id,
		'intention_nodes': [failed_node],
		'session_id': None,
	}
	baseline_a = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_a)
	exec_a = wait_for_single_execution(headers, baseline_a, time.monotonic() + 240)

	hiq = node_output(exec_a, 'Handler: Intention Query')
	if not hiq:
		print('not ok - Handler: Intention Query did not run for the informational question about the failed node')
		return False

	na = node_output(exec_a, 'Execute Workflow: Output & Delivery') or {}
	turn_b = {
		**base_payload,
		'message': 'la fecha requerida es 2026-09-15',
		'parent_override_id': na.get('parent_override_id'),
		'intention_nodes': na.get('intention_nodes'),
		'session_id': None,
	}
	baseline_b = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_b)
	exec_b = wait_for_single_execution(headers, baseline_b, time.monotonic() + 240)

	decode_out = node_output(exec_b, 'Register Intention Node')
	if not decode_out:
		print('not ok - Register Intention Node did not run — the correction was never matched as a retry of the same process')
		return False
	new_node = next((n for n in (decode_out.get('intention_nodes') or []) if n.get('parent_id') == failed_id), None)
	if not new_node:
		print('not ok - no new node was parented under the failed node')
		return False
	inherited = new_node.get('form_state') or {}
	for key in ('Supplier', 'Comments', 'items'):
		if inherited.get(key) != original_form_state.get(key):
			print(f'not ok - inherited form_state.{key} does not match the original request: '
				  f'{inherited.get(key)!r} != {original_form_state.get(key)!r}')
			return False

	nr = node_output(exec_b, 'Execute Workflow: Output & Delivery') or {}
	final_nodes = nr.get('intention_nodes') or []
	final_node = next((n for n in final_nodes if n.get('parent_id') == failed_id), None)
	message = nr.get('message') or ''
	print('Turn B final state: node status=', (final_node or {}).get('status'), 'message=', repr(message))

	if not final_node or final_node.get('status') != 'completed':
		print(f'not ok - retry did not actually succeed in SAP: node status={(final_node or {}).get("status")!r}, '
			  f'message={message!r}')
		return False
	if 'DocNum' not in message and 'ha sido creada' not in message and 'se ha creado' not in message:
		print(f'not ok - node status is completed but the response does not read like a real SAP success: {message!r}')
		return False

	print(f'ok - failed node {failed_id} was loaded, corrected, resubmitted, and genuinely succeeded in SAP: {message!r}')
	return True


def test_readonly_request_after_failure(client, headers, base_payload):
	"""Regression test for a real production incident: after a failed submission, a purely
	informational follow-up ('mostrame el detalle de la solicitud') was being silently
	reprocessed as another submit attempt instead of being answered, because (a) Handler:
	Error left form_state.ready stuck true after the failure, which made the next turn's
	Classify Intent jump straight back into resubmitting before the user's new message was
	ever read, and (b) Agent: Form's own auto-confirm rule didn't check whether the message
	was actually asking to see the data vs. providing/confirming it. Uses a deliberately
	nonexistent ItemCode so the correction genuinely fails again in SAP — this test is about
	the read-only follow-up being answered correctly, not about a create succeeding.
	"""
	failed_id = 'e2e_readonly#0'
	original_form_state = {
		'Supplier': 'C30715652664',
		'Comments': 'E2E read-only-after-failure test.',
		'DocDate': MOST_RECENT_BUSINESS_DAY,
		'items': [{
			'ItemCode': 'NP-9999', 'Quantity': 8, 'LineVendor': 'P30679718378',
			'CostingCode': 'SupplyC', 'CostingCode2': 'ShareSer',
		}],
		'ready': False,
	}
	failed_node = {
		'id': failed_id, 'parent_id': None, 'process_id': 1,
		'process_definition': {'id': 1, 'name': 'Create Purchase Request'},
		'form_state': original_form_state, 'status': 'failed',
		'error_detail': "El servidor SAP devolvió: 'Required date is missing'. Falta el campo Required Date.",
	}
	print(f'\n=== Read-only-request-after-failure: node {failed_id} ===')

	turn_a = {
		**base_payload,
		'message': 'la fecha requerida es 2026-09-20',
		'active_node_override': failed_id,
		'intention_nodes': [failed_node],
		'session_id': None,
	}
	baseline_a = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_a)
	exec_a = wait_for_single_execution(headers, baseline_a, time.monotonic() + 240)

	na = node_output(exec_a, 'Execute Workflow: Output & Delivery') or {}
	nodes_a = na.get('intention_nodes') or []
	new_node_a = next((n for n in nodes_a if n.get('parent_id') == failed_id), None)
	if not new_node_a:
		print('not ok - no new node was parented under the failed node in turn A')
		return False
	if new_node_a.get('status') != 'failed':
		print(f'not ok - expected turn A to genuinely fail again (nonexistent ItemCode), got status={new_node_a.get("status")!r} '
			  f'— this scenario is only meaningful if the corrected submission still fails in SAP')
		return False
	if (new_node_a.get('form_state') or {}).get('ready') is not False:
		print(f'not ok - after the failed submission, form_state.ready was left {(new_node_a.get("form_state") or {}).get("ready")!r} '
			  f'instead of false — the next turn would short-circuit straight back into resubmitting')
		return False
	print(f'ok - turn A failed as expected (bad ItemCode) and ready was correctly reset to false')

	retry_id = new_node_a['id']
	turn_b = {
		**base_payload,
		'message': 'mostrame el detalle de la solicitud',
		'parent_override_id': na.get('parent_override_id'),
		'intention_nodes': nodes_a,
		'session_id': None,
	}
	baseline_b = client.get_latest_execution_id(ORBOT_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, turn_b)
	exec_b = wait_for_single_execution(headers, baseline_b, time.monotonic() + 240)

	if node_output(exec_b, 'Agent: Execute') is not None:
		print('not ok - a purely informational request re-triggered a real SAP execute attempt instead of just answering it')
		return False

	nb = node_output(exec_b, 'Execute Workflow: Output & Delivery') or {}
	message_b = nb.get('message') or ''
	print('Turn B (read-only) message:', repr(message_b))
	if 'NP-9999' not in message_b and '2026-09-20' not in message_b and 'C30715652664' not in message_b:
		print(f'not ok - the read-only request was not answered with the actual current data: {message_b!r}')
		return False

	print(f"ok - 'mostrame el detalle' after a failure was answered directly with the current data instead of "
		  f"re-triggering another submit attempt")
	return True


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
			f'de compra requeridas. Usa {MOST_RECENT_BUSINESS_DAY} como fecha del documento (DocDate) '
			'para cada una.'
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

	summary_state = node_output(execution, 'Execute Workflow: Output & Delivery') or {}
	intention_nodes = summary_state.get('intention_nodes') or []
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

	failed_node = next((node for node in batch_nodes if node.get('status') == 'failed'), None)
	if failed_node:
		base_payload = {
			'expertise_level': payload['expertise_level'],
			'group_name': payload['group_name'],
			'organization': payload['organization'],
			'session': payload['session'],
			'intention_nodes': intention_nodes,
		}
		if not test_retry_after_failure(client, headers, base_payload, failed_node):
			failures.append('retry-after-failure flow did not correctly re-parent and inherit the failed node\'s data')
	else:
		failures.append('no failed batch node found to run the retry-after-failure flow against')

	manual_base_payload = {
		'expertise_level': payload['expertise_level'],
		'group_name': payload['group_name'],
		'organization': payload['organization'],
		'session': payload['session'],
	}
	if not test_manual_retry_succeeds(client, headers, manual_base_payload):
		failures.append('a node that failed only due to a missing field could not be loaded, corrected, and resubmitted to a genuine SAP success')

	if not test_readonly_request_after_failure(client, headers, manual_base_payload):
		failures.append('a purely informational follow-up after a failed submission was not answered directly (either ready stayed stuck true, or it re-triggered another submit attempt)')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - batch execution processed all 4 items sequentially (3 completed, 1 failed), '
		  f'session_id={session_id}')


if __name__ == '__main__':
	main()
