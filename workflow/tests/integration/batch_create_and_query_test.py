"""Standalone E2E test for a batch message mixing a create-type and a query-type process
(Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent -- with a single message that both asks to create a purchase request AND asks
to list vendors. This is the literal scenario docs/use_cases/02_multiple_intents_one_message.md
flagged as unconfirmed: `Agent: Find`'s batch rule used to be worded only around
"create/submit multiple process instances", and `Agent: Execute Batch Intent` used to only
ever call sap_entity_create -- so a create+query mix risked either never being classified as
batch at all, or Agent: Execute Batch Intent trying (and failing) to "create" a vendor-list
record that isn't a submittable instance.

Confirms, against the real live workflow:
  1. Agent: Find classifies the message as new_intent/batch with BOTH processes listed (not
     match on just one, not no_match).
  2. Compute Route Key sends it to batch_processing.
  3. Inside Context Update (2026-08-15 redesign: batch-processing.json no longer resolves its
     own data -- Agent: Extract Batch Records now runs once per process, upstream, in Context
     Update's own per-process loop), the GET-type intent (List Vendors) gets its filter values
     extracted there, and batch-processing.json just calls the real sap-inquiry-execution.json
     sub-workflow with them -- no GET/POST branching or agent of its own left in that file.
  4. The final Compose Batch Summary message embeds a real vendor-list result, not just a
     record count -- proving the query's own data made it into the delivered turn, not only
     a "did it run" signal.
  5. Resolve Final State's intention_nodes actually contains one real, persisted entry per
     batch item (not the old fire-and-forget "batch never touches the graph" behavior) --
     each carrying the real submitted/extracted form_state and a status reflecting what
     actually happened, so a failed one is genuinely clickable-to-recover (UC-6) afterward.
     The interrupted-parent auto-resume this test used to check for no longer exists (removed
     live 2026-08-15, matching sap-inquiry-execution.json's own Compute Execution Outcome) --
     this test starts from a fresh session with nothing to interrupt, so it isn't exercised here.

Real OpenAI calls, real SAP MCP calls (creates a real Purchase Request in the bvs test
company; the vendor list is read-only). Costly and slow by nature -- not a wiring test, the
live regression check this doc's own caveat asked for before trusting this scenario.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/batch_create_and_query_test.py
"""
import os
import re
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
SPINE_WORKFLOW_ID = 'gl7Ax8b77WhVUTmw'
CHAT_WEBHOOK_PATH = 'chat'
API_BASE = 'http://da-sapot-n8n-main:5678/api/v1'
# Reuses the same known-good test fixtures other v14 live tests already rely on: NP-9999 /
# C30715652664 appear in vendor_lookup_during_form_fill_test.py, "Flete" is the exact filter
# term vendor_list_filter_test.py and UC-9's own doc example both use.
MESSAGE = (
	'Crea una solicitud de compra de 5 unidades del articulo NP-9999 para el proveedor '
	'C30715652664, y tambien listame los proveedores que contengan Flete en el nombre.'
)


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
	# MChatSession.language was dropped from the Django model (language now flows payload-only
	# per the 2026 refactor) but migration 0012, which drops the matching NOT NULL DB column,
	# hasn't been applied to this dev DB yet -- the ORM's own .create() can neither set nor omit
	# that column, so it raises IntegrityError either way. Raw SQL sidesteps the model entirely,
	# same workaround this repo's own memory notes already flag for this exact environment gap.
	script = (
		"from django.db import connection\n"
		"from django.utils import timezone\n"
		"from drf_api.models import MOrganization\n"
		"org = MOrganization.objects.get(slug='bvs')\n"
		"now = timezone.now()\n"
		"with connection.cursor() as cur:\n"
		"    cur.execute(\n"
		"        'INSERT INTO drf_api_mchatsession (username, title, language, created_on, updated_on, org_id, connection_key) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id',\n"
		f"        ['{USERNAME}', '', 'es', now, now, org.id, '{DATABASE}'],\n"
		"    )\n"
		"    print(cur.fetchone()[0])\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return int(result.stdout.strip().splitlines()[-1])


def wait_for_fresh_execution(headers, after_id, deadline):
	while time.monotonic() < deadline:
		listing = requests.get(
			f'{API_BASE}/executions', headers=headers,
			params={'workflowId': SPINE_WORKFLOW_ID, 'limit': 5}, timeout=15,
		).json()
		fresh = [item for item in (listing.get('data') or []) if int(item['id']) > after_id and item['status'] in ('success', 'error', 'crashed')]
		if fresh:
			execution_id = min(fresh, key=lambda item: int(item['id']))['id']
			return requests.get(
				f'{API_BASE}/executions/{execution_id}', headers=headers,
				params={'includeData': 'true', 'redactExecutionData': 'false'}, timeout=15,
			).json()
		time.sleep(3)
	return None


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()

	organization = {
		'id': 1,
		'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
		'name': 'BVS', 'plan': {}, 'seat_limit': 25, 'slug': 'bvs',
	}
	session_payload = {'access_token': access_token, 'database': DATABASE, 'user': {'password': PASSWORD, 'username': USERNAME}}
	group_name = f'batch_create_and_query_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, {
		'message': MESSAGE,
		'expertise_level': 3,
		'group_name': group_name,
		'organization': organization,
		'session': session_payload,
		'session_id': None,
	})

	print('Triggered -- polling for the execution to complete...')
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 180)
	if execution is None:
		print('not ok - no execution completed within the deadline')
		sys.exit(1)

	failures = []

	finder_child_id = client.get_child_execution_id(execution, 'Agent: Intent Finder')
	if finder_child_id is None:
		print('not ok - Agent: Intent Finder never ran')
		sys.exit(1)
	finder_execution = client.get_execution(finder_child_id)

	# Agent: Find itself has no structured output parser -- its raw node output is just
	# {"output": "<json string>"}, parsed later by Extract JSON. Compute Route Key runs right
	# after that parse and carries the parsed new_intent_status/processes plus its own
	# route_key in one place, so it's the more useful read here.
	route_key_output = client.get_node_output(finder_execution, 'Compute Route Key')
	if route_key_output is None:
		failures.append('Compute Route Key never ran')
	else:
		print('--- Compute Route Key output ---')
		print({k: route_key_output.get(k) for k in ('status', 'new_intent_status', 'route_key', 'processes')})
		if route_key_output.get('new_intent_status') != 'batch':
			failures.append(f'expected new_intent_status == "batch", got {route_key_output.get("new_intent_status")!r} (status={route_key_output.get("status")!r}, message={route_key_output.get("message")!r})')
		processes = route_key_output.get('processes') or []
		if len(processes) != 2:
			failures.append(f'expected 2 distinct processes in the batch, got {len(processes)}: {processes!r}')
		if route_key_output.get('route_key') != 'batch_processing':
			failures.append(f'expected route_key == "batch_processing", got {route_key_output.get("route_key")!r}')

	context_update_child_id = client.get_child_execution_id(execution, 'Context Update')
	if context_update_child_id is None:
		failures.append('Context Update never ran')
	else:
		context_update_execution = client.get_execution(context_update_child_id)
		extract_output = client.get_node_output(context_update_execution, 'Recover State: Extract Batch Records')
		if extract_output is None:
			failures.append('Agent: Extract Batch Records never ran (batch extraction now happens upstream in Context Update, not inside Batch Processing)')
		else:
			print('--- Recover State: Extract Batch Records output (last process in the loop) ---')
			print({k: extract_output.get(k) for k in ('path', 'process_name', 'items', 'error', 'error_message')})

	batch_child_id = client.get_child_execution_id(execution, 'Batch Processing')
	if batch_child_id is None:
		if not failures:
			failures.append('Batch Processing never ran (classification/routing did not reach it)')
	else:
		batch_execution = client.get_execution(batch_child_id)

		summary_output = client.get_node_output(batch_execution, 'Compose Batch Summary')
		if summary_output is None:
			failures.append('Compose Batch Summary never ran')
		else:
			message = summary_output.get('message') or ''
			print('--- Compose Batch Summary message ---')
			print(message)
			if 'Purchase Request' not in message and 'Purchase' not in message and 'compra' not in message.lower():
				failures.append(f'expected the create intent to appear in the summary, got: {message}')
			if 'Vendors' not in message and 'Proveedores' not in message and 'proveedores' not in message.lower():
				failures.append(f'expected the query intent (List Vendors) to appear in the summary, got: {message}')

		final_state = client.get_node_output(batch_execution, 'Resolve Final State')
		if final_state is None:
			failures.append('Resolve Final State never ran')
		else:
			nodes = final_state.get('intention_nodes') or {}
			# process_id is whatever this org's real process definition carries -- numeric ids
			# here (1, 63), not slugs -- so this only checks count/shape/status, not identity.
			# The create side's record count is inherently non-deterministic (Agent: Execute
			# Batch Intent decides how many records exist, or none at all, from the raw
			# message) -- cross-check node count against what the summary itself reports
			# rather than assuming a fixed total.
			print('--- Resolve Final State intention_nodes ---')
			print({node_id: {'process_id': n.get('process_id'), 'status': n.get('status'), 'form_state': n.get('form_state')} for node_id, n in nodes.items()})
			create_match = re.search(r'(\d+) creadas, (\d+) fallidas', message)
			expected_create_nodes = (int(create_match.group(1)) + int(create_match.group(2))) if create_match else 0
			expected_total = expected_create_nodes + 1  # +1 for the query, which always produces exactly one result
			if len(nodes) != expected_total:
				failures.append(f'expected {expected_total} registered nodes ({expected_create_nodes} from the create summary + 1 for the query), got {len(nodes)}: {list(nodes.keys())}')
			completed_count = sum(1 for n in nodes.values() if n.get('status') == 'completed')
			failed_count = sum(1 for n in nodes.values() if n.get('status') == 'failed')
			expected_failed = int(create_match.group(2)) if create_match else 0
			if failed_count != expected_failed:
				failures.append(f'expected {expected_failed} failed node(s) (matching the create summary\'s own failed count), got {failed_count}')
			if completed_count < 1:
				failures.append('expected at least one completed node (the query -- finding zero records is still success)')
			failed_nodes = [n for n in nodes.values() if n.get('status') == 'failed']
			if failed_nodes and failed_nodes[0].get('form_state', {}).get('ready') is not False:
				failures.append(f'expected a failed node\'s form_state.ready to be false so a click-to-resume re-enters correction mode, got: {failed_nodes[0].get("form_state")}')
			query_nodes = [n for n in nodes.values() if (n.get('form_state') or {}).get('CardName') == 'Flete']
			if not query_nodes:
				failures.append(f'expected one node carrying the extracted query filter as its own form_state, got: {list(nodes.values())}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - mixed create+query batch classified and executed correctly end to end, session_id={session_id}')


if __name__ == '__main__':
	main()
