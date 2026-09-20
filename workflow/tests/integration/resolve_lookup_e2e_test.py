"""Live E2E check for the autonomous name->code resolve feature (Orbot v14).

Exercises the REAL, live spine workflow end-to-end -- real OpenAI calls, real SAP B1 Service
Layer calls, no pins, no disposable workflow copy. This is Phase 5 of the resolve-feature plan:
send the message that originally crashed with a raw SAP HTTP 400 ("GroupCode eq no productivos",
unquoted, because GroupCode is schema-typed number and the string filter builder never ran), and
confirm the agent now autonomously resolves the group name to its numeric code first (one extra
sap_query_entity_set call against BusinessPartnerGroups), then retries the original query, within
the same turn -- exactly two tool calls total, no user intervention.

Two turns:
    1. The exact originally-failing message. Whatever the actual outcome (a real match, or a
       clean 0-match if "no productivos" doesn't exist on this tenant), the point is: no raw SAP
       error should ever reach the user, and if resolution fires, it should be a 2-call sequence.
    2. A deliberately collision-prone group name ("Sin definir") that Track B confirmed exists
       TWICE on this tenant -- once as a vendor group (Code 122) and once as a customer group
       (Code 124, name "Sin definir." with a trailing period). This is the strongest available
       proof that the resolve block's default_filters (Type eq bbpgt_VendorGroup) actually
       disambiguates correctly, since match_type defaults to `contains` and "Sin definir." also
       contains "Sin definir" as a substring -- an unconstrained lookup would be a coin flip.

This is intentionally NOT a pinned regression test (no pins, no assert-and-exit) -- it's a
one-shot diagnostic run meant to be read by a human/agent afterward, because a single LLM turn's
exact tool-call sequence isn't something a fixed assertion should try to pin down in general.

Run directly inside the backend container:
    python3 /home/workflow/tests/integration/resolve_lookup_e2e_test.py
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
SPINE_WORKFLOW_ID = 'gl7Ax8b77WhVUTmw'
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
	while time.monotonic() < deadline:
		messages = get_messages(access_token, session_id)
		non_status = [m for m in messages if m.get('type') != 'status']
		if len(non_status) > before_count:
			return non_status[-1]
		time.sleep(2)
	return None


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


def inspect_inquiry_execution(client, spine_execution):
	"""Drill into the 'SAP: Inquiry Execution' sub-execution and report the SAP MCP tool call
	sequence plus the Build Execution Prompt chatInput that drove it -- everything needed to tell
	whether resolution fired and behaved correctly.

	For a GET-type process reached via form-filling (the common case -- e.g. a query.filters
	value like GroupCode still needs collecting/confirming), the spine calls 'SAP: Process Form
	Filling' first, which only THEN calls 'SAP: Inquiry Execution' itself as its own nested
	Execute Workflow node ('Execute Workflow: SAP Inquiry Execution' in
	sap-process-form-filling.json) -- a grandchild of the spine execution, not a direct child.
	Try the direct link first (in case a future flow ever calls it straight from the spine), fall
	back to the two-hop path through form-filling."""
	child_id = client.get_child_execution_id(spine_execution, 'SAP: Inquiry Execution')
	if not child_id:
		form_filling_id = client.get_child_execution_id(spine_execution, 'SAP: Process Form Filling')
		if not form_filling_id:
			return None
		form_filling_execution = client.get_execution(form_filling_id)
		child_id = client.get_child_execution_id(form_filling_execution, 'Execute Workflow: SAP Inquiry Execution')
		if not child_id:
			return None
	child = client.get_execution(child_id)
	run_data = child.get('data', {}).get('resultData', {}).get('runData', {})

	build_prompt_output = client.get_node_output(child, 'Build Execution Prompt')
	chat_input = (build_prompt_output or {}).get('chatInput')

	mcp_runs = run_data.get('SAP MCP') or []
	mcp_calls = []
	for run in mcp_runs:
		# LangChain tool nodes store their invocation under the 'ai_tool' connection type, not
		# 'main' -- inputOverride.ai_tool is the exact call the agent made (serviceName/filter/
		# etc.), data.ai_tool is what the tool returned to it. Confirmed against a real run.
		input_items = (run.get('inputOverride', {}).get('ai_tool') or [[]])[0] or []
		output_items = (run.get('data', {}).get('ai_tool') or [[]])[0] or []
		mcp_calls.append({
			'input': input_items[0]['json'] if input_items else None,
			'output': output_items[0]['json'] if output_items else None,
		})

	agent_runs = run_data.get('Agent: Execute') or []
	agent_output = None
	if agent_runs:
		items = (agent_runs[-1].get('data', {}).get('main') or [[]])[0] or []
		agent_output = items[0]['json'] if items else None

	return {
		'child_execution_id': child_id,
		'chat_input': chat_input,
		'mcp_call_count': len(mcp_runs),
		'mcp_calls': mcp_calls,
		'agent_execute_output': agent_output,
	}


def send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name):
	payload = {
		'active_node_id': None,
		'bucket_file_ids': [],
		'expertise_level': 3,
		'group_name': group_name,
		'intention_nodes': {},
		'language': 'es',
		'message': message,
		'organization': organization,
		'session': session_payload,
		'session_id': session_id,
	}
	before_count = len([m for m in get_messages(access_token, session_id) if m.get('type') != 'status'])
	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 150)
	if execution is None:
		return None, None
	delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
	return execution, delivered


def run_one(client, headers, access_token, session_id, organization, session_payload, label, message):
	print(f'\n{"=" * 100}\nTURN: {label}\nmessage: {message!r}\n{"=" * 100}')
	group_name = f'resolve_e2e_test_{session_id}_{label}_{int(time.time())}'
	execution, delivered = send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name)

	if execution is None:
		print('RESULT: no spine execution completed within timeout')
		return

	print(f"spine execution: id={execution.get('id')} status={execution.get('status')}")

	if delivered:
		print(f"delivered message: {json.dumps(delivered.get('content') or delivered, ensure_ascii=False, indent=2)[:3000]}")
	else:
		print('warning: spine execution finished but no non-status message was confirmed delivered within 30s')

	detail = inspect_inquiry_execution(client, execution)
	if detail is None:
		print("RESULT: this turn never reached 'SAP: Inquiry Execution' at all (did earlier routing/form-filling handle it differently?)")
		return

	print(f"\nSAP: Inquiry Execution child execution id: {detail['child_execution_id']}")
	print(f"SAP MCP tool call count: {detail['mcp_call_count']}")
	for i, call in enumerate(detail['mcp_calls'], 1):
		print(f"  call {i} input: {json.dumps(call['input'], ensure_ascii=False)[:1500]}")
		print(f"  call {i} output: {json.dumps(call['output'], ensure_ascii=False)[:1500]}")
	print(f"\nAgent: Execute final output: {json.dumps(detail['agent_execute_output'], ensure_ascii=False, indent=2)[:2000]}")
	if detail['chat_input'] and 'RESOLVABLE FIELDS' in detail['chat_input']:
		print('\nBuild Execution Prompt DID surface a RESOLVABLE FIELDS section this turn (resolution was offered to the agent).')
	else:
		print('\nBuild Execution Prompt did NOT surface a RESOLVABLE FIELDS section this turn (fast path or no resolve field matched).')


def main():
	session_data = django_login()
	access_token = session_data['access_token']
	session_id = create_test_session()
	print(f'logged in, test session_id={session_id}')

	organization = {
		'id': 1,
		'integration': {'auth_driver': 'b1s', 'base_url': 'https://10.240.1.23:50000/b1s/v1/', 'target': 'b1s'},
		'name': 'BVS', 'plan': {}, 'seat_limit': 25, 'slug': 'bvs',
	}
	session_payload = {'access_token': access_token, 'database': DATABASE, 'user': {'password': PASSWORD, 'username': USERNAME}}

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	run_one(
		client, headers, access_token, session_id, organization, session_payload,
		label='original_bug_report',
		message='Listame los proveedores que pertenezcan al grupo no productivos',
	)

	run_one(
		client, headers, access_token, session_id, organization, session_payload,
		label='collision_disambiguation',
		message='Listame los proveedores del grupo Sin definir',
	)

	print(f'\n{"=" * 100}\ndone, session_id={session_id}\n{"=" * 100}')


if __name__ == '__main__':
	main()
