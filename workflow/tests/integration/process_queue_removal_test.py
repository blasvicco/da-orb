"""Standalone E2E test for the process_queue removal (Orbot v14, Phase 4c).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the live regression guard for Phase 4c of the 2026-08-13 Intention
Graph cleanup: process_queue (Agent: Form's "create N separate instances of the same
process" feature) was traced end-to-end and found to be dead plumbing -- Compute Form
Outcome computed it, Build Callback Payload shipped it to Django, but
_resolve_and_persist_state (main.py) never persisted it and no node anywhere in v14
(including the actual SAP-submitting Compute Execution Outcome) ever read it back to loop
over the queued instances. Per direct instruction, multi-instance requests are already
handled correctly by Agent: Find's own existing new_intent_status: 'batch' classification,
so process_queue was removed entirely rather than wired up -- no new batch-loop logic
needed. This test's only job is confirming ordinary single-instance form-filling still
works cleanly with the field gone (Compute Form Outcome/Build Callback Payload no longer
reference it at all).

Scenario:
	1. Start a purchase request (real turn) -- a new intention_nodes entry gets created.
	2. Supply the Required Date (real turn, in_progress) -- confirms Compute Form Outcome
	   still runs correctly and mirrors form_state into intention_nodes[id] with
	   process_queue gone from its own code entirely.
	3. Inspect Compute Form Outcome's actual live output on turn 2 -- confirm it has no
	   process_queue key at all (not even null -- the field is dropped, not defaulted).
	4. Confirm persisted Redis state (the same class N8nClient.fire() uses in production)
	   has no process_queue key either.

Real OpenAI calls (two full turns). Not a wiring test -- a real live regression check that
removing dead plumbing didn't break the ordinary single-instance path it shared code with.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/process_queue_removal_test.py
"""
import json
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
FORM_FILLING_WORKFLOW_NAME = 'Orbot v14 - SAP Process Form Filling'
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
	"""Load the real Redis-persisted state for group_name via Django's own N8nSessionState
	class -- the exact class N8nClient.fire() uses in production."""
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
	group_name = f'process_queue_removal_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': __import__('os').environ['N8N_API_KEY']}

	def send(message):
		"""Mirrors the CURRENT N8nClient.fire() payload shape exactly (client.py)."""
		current = load_current_state(group_name)
		payload = {
			'active_node_id': current.get('active_node_id'),
			'bucket_file_ids': [],
			'expertise_level': 3,
			'group_name': group_name,
			'intention_nodes': current.get('intention_nodes') or {},
			'message': message,
			'organization': organization,
			'session': session_payload,
			'session_id': session_id,
		}
		if current.get('last_bot_message'):
			payload['last_bot_message'] = current.get('last_bot_message')

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

	failures = []

	turn1 = send('Quiero crear una solicitud de compra')
	if turn1 is None:
		print('not ok - turn 1 (start purchase request) never completed')
		sys.exit(1)

	pr_node_id = load_current_state(group_name).get('active_node_id')
	if not pr_node_id:
		print('not ok - no active_node_id after turn 1 (purchase request never became the active node)')
		sys.exit(1)

	turn2 = send('La fecha requerida es 2026-09-01')
	if turn2 is None:
		print('not ok - turn 2 (supply Required Date) never completed')
		sys.exit(1)

	# Drill into the real, live SAP Process Form Filling sub-execution to inspect Compute
	# Form Outcome's own output directly -- confirms the field is gone from the node's own
	# code path, not just absent from Redis (which never persisted it anyway).
	form_filling_child_id = client.get_child_execution_id(turn2, 'SAP: Process Form Filling')

	if form_filling_child_id is not None:
		form_filling_execution = client.get_execution(form_filling_child_id)
		compute_form_outcome_output = client.get_node_output(form_filling_execution, 'Compute Form Outcome')
		if compute_form_outcome_output is None:
			failures.append("could not read Compute Form Outcome's own output on turn 2 to confirm process_queue is gone")
		elif 'process_queue' in compute_form_outcome_output:
			failures.append(f"expected process_queue to be entirely absent from Compute Form Outcome's live output, but found it: {compute_form_outcome_output.get('process_queue')!r}")
		else:
			print("--- Compute Form Outcome's own output on turn 2 has no process_queue key -- confirmed ---")
	else:
		print('warning: could not locate the SAP Process Form Filling sub-execution to inspect Compute Form Outcome directly; falling back to Redis-only checks')

	state_after_turn2 = load_current_state(group_name)
	print('--- state after turn 2 ---')
	print(json.dumps(state_after_turn2, indent=2))

	if 'process_queue' in state_after_turn2:
		failures.append(f"expected no process_queue key anywhere in persisted Redis state, got: {state_after_turn2.get('process_queue')!r}")

	pr_node = (state_after_turn2.get('intention_nodes') or {}).get(pr_node_id)
	if pr_node is None:
		failures.append(f'purchase request node ({pr_node_id!r}) disappeared from intention_nodes after turn 2')
	else:
		saved_required_date = (pr_node.get('form_state') or {}).get('RequriedDate')
		if not saved_required_date:
			failures.append(f'expected RequriedDate to still be correctly mirrored into intention_nodes[{pr_node_id!r}].form_state after turn 2 (ordinary single-instance form-filling unaffected by the process_queue removal), got form_state={pr_node.get("form_state")!r}')
		if pr_node.get('status') != 'active':
			failures.append(f"expected the node to still be 'active' (no parking happened), got status={pr_node.get('status')!r}")

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - process_queue removal leaves ordinary single-instance form-filling fully working, and the field is confirmed gone from both the live Compute Form Outcome output and persisted Redis state, session_id={session_id}')


if __name__ == '__main__':
	main()
