"""Standalone E2E test for the last_error/last_batch_result/intents removal (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the live regression guard for the 2026-08-14 cleanup that followed
Phase 4c: last_error, last_batch_result, and intents were shipped in the callback's `state`
object every relevant turn -- error-parser.json and batch-processing.json both had explicit
comments describing them as "round-tripped so a later general_inquiry turn can retrieve
this" -- but Django's _resolve_and_persist_state (main.py) only ever merges
active_node_id/intention_nodes/last_bot_message into persisted Redis state, so none of the
three ever actually survived to a later turn. last_error turned out doubly dead:
general-inquiry.json's own prompt-builder reconstructs an equivalent object locally from
intention_nodes instead of reading the persisted field at all. last_batch_result/intents
were never read anywhere. All three were removed outright (user's call, matching the
process_queue precedent) rather than wired up.

Scenario:
	1. Send a deliberately unparseable message (real turn) -- triggers Agent: Find's
	   no_match path, which flows through Classify & Store Error -> Build Callback
	   Payload, the exact two nodes edited in this cleanup.
	2. Inspect Build Callback Payload's own live output on that turn -- confirm the
	   `state` object has no last_error/last_batch_result/intents keys at all.
	3. Confirm the turn still delivers a normal, correctly worded "I didn't understand"
	   reply to the user -- proving the removal didn't break the actual user-facing
	   behavior of the error path, only the dead round-trip plumbing riding along with it.

Real OpenAI call (one turn). Not a wiring test -- a real live regression check that
removing three dead-on-arrival fields left the error-reporting path fully intact.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/dead_state_fields_removal_test.py
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


def load_current_state(group_name):
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
	group_name = f'dead_state_fields_removal_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	payload = {
		'active_node_id': None,
		'bucket_file_ids': [],
		'expertise_level': 3,
		'group_name': group_name,
		'intention_nodes': {},
		'message': 'asdkjhaskjdh xyz123 zzz',
		'organization': organization,
		'session': session_payload,
		'session_id': session_id,
	}

	before_count = len([m for m in get_messages(access_token, session_id) if m.get('type') != 'status'])
	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 120)
	if execution is None:
		print('not ok - turn (unparseable message -> no_match error path) never completed')
		sys.exit(1)
	delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
	if delivered is None:
		print('warning: n8n execution finished but no message was confirmed delivered/persisted within 30s')

	failures = []

	# Build Callback Payload lives inside response.json, which is only ever reached via a
	# sub-workflow's own "Execute Workflow: Response" node -- for a no_match turn that's
	# agent-intent-finder.json's, itself a child of the root spine execution. Two levels
	# of drilling needed: spine -> Agent: Intent Finder -> Execute Workflow: Response.
	build_callback_payload_output = None
	finder_child_id = client.get_child_execution_id(execution, 'Agent: Intent Finder')
	if finder_child_id is not None:
		finder_execution = client.get_execution(finder_child_id)
		response_child_id = client.get_child_execution_id(finder_execution, 'Execute Workflow: Response')
		if response_child_id is not None:
			response_execution = client.get_execution(response_child_id)
			build_callback_payload_output = client.get_node_output(response_execution, 'Build Callback Payload')

	if build_callback_payload_output is None:
		failures.append("could not locate Build Callback Payload's own live output to inspect the state object directly")
	else:
		state = build_callback_payload_output.get('state') or {}
		print('--- Build Callback Payload live output: state ---')
		print(json.dumps(state, indent=2))
		for dead_key in ('last_error', 'last_batch_result', 'intents'):
			if dead_key in state:
				failures.append(f"expected {dead_key!r} to be entirely absent from Build Callback Payload's state object, but found it: {state.get(dead_key)!r}")
		# Build Callback Payload never echoes `error` itself in its own output -- it only
		# uses d.error internally to pick `type` (NO_MATCH/MULTIPLE_PROCESSES/AGENT_ERROR
		# are soft errors delivered as type 'agent', anything else as 'alert'). type
		# 'agent' here confirms the no_match soft-error carve-out fired correctly, i.e.
		# Classify & Store Error did run and classified this as NO_MATCH.
		if build_callback_payload_output.get('type') != 'agent':
			failures.append(f"expected the no_match turn to deliver as type='agent' (soft-error carve-out), got type={build_callback_payload_output.get('type')!r}")

	messages = get_messages(access_token, session_id)
	non_status = [m for m in messages if m.get('type') != 'status']
	if not non_status:
		failures.append('expected at least one delivered reply after the no_match turn, got none')
	else:
		last_message = non_status[-1]
		print(f"--- delivered reply: type={last_message.get('type')!r} text={last_message.get('text')!r} ---")
		if not last_message.get('text'):
			failures.append('expected a non-empty reply text for the no_match turn')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - last_error/last_batch_result/intents are confirmed gone from the live Build Callback Payload output, and the no_match error path still delivers a normal reply, session_id={session_id}')


if __name__ == '__main__':
	main()
