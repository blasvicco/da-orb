"""Standalone E2E test for Agent: Find classifying pending_reply without pending_kind (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the live regression guard for Phase 3 of the 2026-08-13 Intention
Graph cleanup: `pending_kind` (a pure restatement of `process_id && !form_state?.ready`) was
eliminated entirely -- Enrich Context no longer computes it, Compute Route Key no longer
branches on it, and Agent: Find's systemMessage was restructured to reason directly from
`process_id`/`form_state.ready` in the INPUT JSON instead of a derived label. This is the
riskiest part of Phase 3 since it touches Agent: Find's actual classification prompt, the
same prompt that broke once already today on a differently-phrased case -- Tier 1 alone
can't catch a real LLM misreading the restructured instructions.

Scenario:
	1. Start a purchase request (node becomes active, mid-form -- process_id set,
	   form_state.ready not yet true).
	2. Supply the Required Date -- a message that plausibly continues the open form. Assert
	   Agent: Find classifies this turn as "pending_reply" (not "new_intent") purely from
	   process_id/form_state.ready now visible in the INPUT JSON, with no pending_kind field
	   present anywhere in the payload -- and that route_key correctly resolves to
	   sap_form_filling and the field actually lands in form_state.

Real OpenAI calls (two full turns). Costly and slow by nature -- not a wiring test, a real
live regression check for exactly the classification path this session's cleanup touched.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/pending_kind_elimination_test.py
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


def load_current_state(group_name):
	"""Load the real Redis-persisted state for group_name via Django's own N8nSessionState
	class -- the exact class N8nClient.fire() uses in production. This test triggers the
	webhook directly (bypassing fire()), so without this the webhook body would never carry
	prior-turn state at all, unlike a real user's turn, which always goes through fire()."""
	script = (
		"import asyncio, json\n"
		"from web_socket.helpers.n8n.state import N8nSessionState\n"
		"async def _run():\n"
		f"\tstate = N8nSessionState(group_name={group_name!r})\n"
		"\ttry:\n"
		"\t\tdata = await state.load()\n"
		"\tfinally:\n"
		"\t\tawait state.close()\n"
		"\tprint(json.dumps(data))\n"
		"asyncio.run(_run())\n"
	)
	result = subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)
	return json.loads(result.stdout.strip().splitlines()[-1])


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
	group_name = f'pending_kind_elimination_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	def send(message):
		current = load_current_state(group_name)
		payload = {
			'message': message,
			'expertise_level': 3,
			'group_name': group_name,
			'organization': organization,
			'session': session_payload,
			'session_id': session_id,
			'active_node_id': current.get('active_node_id'),
			'bucket_file_ids': [],
			'form_state': current.get('form_state'),
			'intention_nodes': current.get('intention_nodes') or [],
			'paused_node_ids': current.get('paused_node_ids') or [],
			'process_id': current.get('process_id'),
		}
		if current.get('last_bot_message'):
			payload['last_bot_message'] = current.get('last_bot_message')
		if current.get('process_definition') is not None:
			payload['process_definition'] = current.get('process_definition')

		before_count = len([m for m in get_messages(access_token, session_id) if m.get('type') != 'status'])
		baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
		client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)
		execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 120)
		if execution is None:
			return None
		delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
		if delivered is None:
			print('warning: n8n execution finished but no message was confirmed delivered/persisted within 30s')
		return execution

	turn1 = send('Quiero crear una solicitud de compra')
	if turn1 is None:
		print('not ok - turn 1 (start purchase request) never completed')
		sys.exit(1)

	state_after_turn1 = load_current_state(group_name)
	if not state_after_turn1.get('process_id'):
		print(f'not ok - no process_id active after turn 1, got state={state_after_turn1!r}')
		sys.exit(1)
	if 'pending_kind' in state_after_turn1:
		print(f"not ok - pending_kind still present in persisted state after turn 1 (should be gone entirely): {state_after_turn1.get('pending_kind')!r}")
		sys.exit(1)

	turn2 = send('La fecha requerida es 2026-09-01')
	if turn2 is None:
		print('not ok - turn 2 (supply Required Date) never completed')
		sys.exit(1)

	failures = []

	finder_child_id = client.get_child_execution_id(turn2, 'Agent: Intent Finder')
	if finder_child_id is None:
		print('not ok - Agent: Intent Finder never ran on turn 2')
		sys.exit(1)
	finder_execution = client.get_execution(finder_child_id)

	find_output = client.get_node_output(finder_execution, 'Agent: Find')
	if find_output is None:
		failures.append('Agent: Find never ran on turn 2')
	else:
		raw = find_output.get('output') or ''
		print(f'--- Agent: Find raw output on turn 2 ---\n{raw}')
		if '"status":"pending_reply"' not in raw.replace(' ', '') and '"status": "pending_reply"' not in raw:
			failures.append(f'expected Agent: Find to classify turn 2 as pending_reply (no pending_kind field to key off anymore, must reason from process_id/form_state.ready) -- got: {raw}')
		if 'pending_kind' in raw:
			failures.append(f'Agent: Find raw output still mentions pending_kind -- OUTPUT contract should no longer include it: {raw}')

	prompt_find_output = client.get_node_output(finder_execution, 'Prompt: Find')
	if prompt_find_output is not None:
		chat_input = prompt_find_output.get('chatInput') or ''
		if '"pending_kind"' in chat_input:
			failures.append('Prompt: Find still includes a pending_kind field in the INPUT JSON sent to the LLM -- Enrich Context should no longer produce it')
		if '"process_id"' not in chat_input:
			failures.append('Prompt: Find INPUT JSON is missing process_id -- Agent: Find cannot reason about an active process without it')

	route_key_output = client.get_node_output(finder_execution, 'Compute Route Key')
	if route_key_output is not None:
		print(f"--- route_key ---\n{route_key_output.get('route_key')}")
		if route_key_output.get('route_key') != 'sap_form_filling':
			failures.append(f"expected route_key sap_form_filling, got {route_key_output.get('route_key')!r}")

	state_after_turn2 = load_current_state(group_name)
	restored_date = (state_after_turn2.get('form_state') or {}).get('RequriedDate')
	print(f"--- form_state after turn 2 ---\n{json.dumps(state_after_turn2.get('form_state'), indent=2)}")
	if restored_date != '2026-09-01':
		failures.append(f"expected RequriedDate 2026-09-01 to land in form_state after turn 2, got {restored_date!r}")

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - Agent: Find correctly classifies pending_reply without pending_kind, session_id={session_id}')


if __name__ == '__main__':
	main()
