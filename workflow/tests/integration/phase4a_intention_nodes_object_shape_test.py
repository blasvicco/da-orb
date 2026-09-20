"""Standalone E2E test for the intention_nodes object-keyed restructure (Orbot v14, Phase 4a).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the live regression guard for Phase 4a of the 2026-08-13 Intention
Graph cleanup: `intention_nodes` was restructured from an array (Node[]) to an object keyed
by each node's own id (Record<id, Node>), and the root-level "working copy"
(process_id/process_definition/form_state, mirrored from whatever node is active) and
`paused_node_ids` were eliminated entirely -- every consumer now reads/writes
intention_nodes[active_node_id] directly. This touched 13 nodes across 8 workflow files
(Initialize Process, Park Current Intent, Resolve Override, Prompt: Context & Conversation,
Build Execution Prompt, Build SAP Payload, Compute Execution Outcome, Reset Form Not Ready,
Prompt: Form, Compute Form Outcome, Classify & Store Error, Build Callback Payload,
Prompt: Intention Focus) plus Django (state.py/client.py/main.py) and the frontend
(stack.js) -- the single largest change of the day, so this test covers the full turn
lifecycle rather than one narrow case.

Scenario:
	1. Start a purchase request (real turn) -- a new intention_nodes entry gets created,
	   confirmed to be a plain dict (object), not a list.
	2. Supply the Required Date (real turn, in_progress, node stays active, no parking) --
	   confirms the mirror-into-intention_nodes[id] step still works with no root-level
	   copy involved at all.
	3. Deterministically park node A and activate a second node B via
	   N8nSessionState.restore -- same technique used for Phase 2's click-to-resume test,
	   isolating Resolve Override's own mechanism from Agent: Find's separately-known
	   classification flakiness.
	4. Send active_node_override targeting node A -- confirms Resolve Override correctly
	   parks node B and reactivates node A by direct key lookup, with form_state intact,
	   under the new object-keyed shape.

Real OpenAI calls (two full turns) plus one deterministic state write and one deterministic
override turn. Costly and slow by nature -- not a wiring test, a real live regression check
for the largest structural change made today.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/phase4a_intention_nodes_object_shape_test.py
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


def restore_state(group_name, state):
	"""Write a state dict directly to Redis via Django's own N8nSessionState.restore --
	used here to deterministically inject a second, already-active intention node without
	depending on Agent: Find's real (separately known-flaky) new_intent classification."""
	state_literal = repr(json.dumps(state))
	script = (
		"import asyncio, json\n"
		"from web_socket.helpers.n8n.state import N8nSessionState\n"
		"async def _run():\n"
		f"\tsession_state = N8nSessionState(group_name={group_name!r})\n"
		"\ttry:\n"
		f"\t\tawait session_state.restore(json.loads({state_literal}))\n"
		"\tfinally:\n"
		"\t\tawait session_state.close()\n"
		"asyncio.run(_run())\n"
	)
	subprocess.run(
		['python', 'manage.py', 'shell', '-c', script],
		cwd='/home/app', capture_output=True, text=True, check=True,
	)


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
	group_name = f'phase4a_object_shape_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	def send(message, active_node_override=None):
		current = load_current_state(group_name)
		payload = {
			'message': message,
			'expertise_level': 3,
			'group_name': group_name,
			'organization': organization,
			'session': session_payload,
			'session_id': session_id,
			'active_node_id': current.get('active_node_id'),
			'active_node_override': active_node_override,
			'bucket_file_ids': [],
			'intention_nodes': current.get('intention_nodes') or {},
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

	state_after_turn1 = load_current_state(group_name)
	print(f"--- state after turn 1 ---\n{json.dumps(state_after_turn1, indent=2)[:800]}")

	if not isinstance(state_after_turn1.get('intention_nodes'), dict):
		print(f"not ok - expected intention_nodes to be a dict (object-keyed), got {type(state_after_turn1.get('intention_nodes'))!r}: {state_after_turn1.get('intention_nodes')!r}")
		sys.exit(1)
	if 'process_id' in state_after_turn1 or 'form_state' in state_after_turn1 or 'process_definition' in state_after_turn1 or 'paused_node_ids' in state_after_turn1:
		failures.append(f"root-level process_id/process_definition/form_state/paused_node_ids should be entirely gone from persisted state, got keys: {list(state_after_turn1.keys())}")

	pr_node_id = state_after_turn1.get('active_node_id')
	if not pr_node_id or pr_node_id not in state_after_turn1.get('intention_nodes', {}):
		print(f"not ok - active_node_id {pr_node_id!r} not found as a key in intention_nodes after turn 1")
		sys.exit(1)

	turn2 = send('La fecha requerida es 2026-09-01')
	if turn2 is None:
		print('not ok - turn 2 (supply Required Date) never completed')
		sys.exit(1)

	state_after_turn2 = load_current_state(group_name)
	pr_node = state_after_turn2.get('intention_nodes', {}).get(pr_node_id)
	print(f"--- purchase request node after turn 2 ---\n{json.dumps(pr_node, indent=2)}")
	if pr_node is None:
		print(f"not ok - node {pr_node_id!r} disappeared from intention_nodes after turn 2")
		sys.exit(1)
	saved_required_date = (pr_node.get('form_state') or {}).get('RequriedDate')
	if not saved_required_date:
		failures.append(f"expected RequriedDate to be mirrored into intention_nodes[{pr_node_id!r}].form_state after turn 2, got form_state={pr_node.get('form_state')!r}")
	if pr_node.get('status') != 'active':
		failures.append(f"expected the node to still be 'active' (no parking happened), got status={pr_node.get('status')!r}")

	node_b_id = 'test_node_b#1'
	parked_pr_node = {**pr_node, 'status': 'paused'}
	node_b = {
		'id': node_b_id, 'parent_id': pr_node_id, 'process_id': 2,
		'process_definition': {'id': 2, 'name': 'List Vendors'},
		'form_state': {'ready': True}, 'status': 'active',
	}
	restore_state(group_name, {
		**state_after_turn2,
		'active_node_id': node_b_id,
		'intention_nodes': {pr_node_id: parked_pr_node, node_b_id: node_b},
	})

	turn3 = send('gracias', active_node_override=pr_node_id)
	if turn3 is None:
		print('not ok - turn 3 (active_node_override click-to-resume) never completed')
		sys.exit(1)

	state_after_turn3 = load_current_state(group_name)
	print(f"--- state after turn 3 (active_node_override resume) ---\n{json.dumps(state_after_turn3, indent=2)}")

	if state_after_turn3.get('active_node_id') != pr_node_id:
		failures.append(f"expected active_node_id to switch back to {pr_node_id!r}, got {state_after_turn3.get('active_node_id')!r}")

	nodes_after_turn3 = state_after_turn3.get('intention_nodes', {})
	pr_node_after = nodes_after_turn3.get(pr_node_id)
	if pr_node_after is None:
		failures.append(f"node {pr_node_id!r} disappeared from intention_nodes after the override resume")
	else:
		if pr_node_after.get('status') != 'active':
			failures.append(f"expected {pr_node_id!r} to be reactivated (status=active), got status={pr_node_after.get('status')!r}")
		restored_date = (pr_node_after.get('form_state') or {}).get('RequriedDate')
		if restored_date != saved_required_date:
			failures.append(f"expected the resumed node's form_state to carry the Required Date from turn 2 ({saved_required_date!r}), got {restored_date!r}")

	node_b_after = nodes_after_turn3.get(node_b_id)
	if node_b_after is None:
		failures.append(f"node B ({node_b_id!r}) disappeared from intention_nodes after the override resume")
	elif node_b_after.get('status') != 'paused':
		failures.append(f"expected node B to be parked (status=paused), got status={node_b_after.get('status')!r}")

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - intention_nodes object-keyed restructure (Phase 4a) works end-to-end, session_id={session_id}')


if __name__ == '__main__':
	main()
