"""Standalone E2E test for click-to-resume via active_node_override (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the regression guard for Phase 2 of the 2026-08-13 Intention Graph
cleanup: the dead conversational stack-resume confirmation flow (Resolve Stack Resume,
Needs Stack Resume?, the frontend's Resume button/emit chain) was removed entirely, since
the user confirmed the ONLY real "go back to a paused intention" mechanism is clicking a
node in the Intention Graph sidebar (active_node_override -> Resolve Override,
intent-manager.json). This test proves that path still works end-to-end after the removal.

Scenario:
	1. Start a purchase request via a real turn (node A becomes active) -- gets a real,
	   live-created node id and process_definition rather than a hand-built fixture.
	2. Supply the Required Date only -- gives node A real, distinguishable form_state to
	   check survives the park/resume round trip.
	3. Directly write a second, already-active node B into Redis via N8nSessionState.restore
	   -- deliberately NOT by sending a real side-query turn and letting Agent: Find
	   classify it as new_intent. That classification is separately known to be flaky (see
	   docs/agent_find_prompt_review_2026-08-13.md's "Status: still open" note) precisely
	   in this mid-form-interrupt scenario, and this test's job is to isolate and verify
	   Resolve Override/Intent Manager's own mechanism, not ride on a second, unrelated
	   LLM classification's non-determinism.
	4. Send active_node_override = node A's id (the real payload shape the frontend sends
	   when a user clicks a graph node, per app/frontend/src/modules/websocket/chat.js) --
	   Resolve Override should park node B, reactivate node A with its saved form_state
	   (Required Date intact), and route straight to sap_form_filling.

Real OpenAI calls (two full turns) plus one deterministic state write and one deterministic
override turn. Costly and slow by nature -- not a wiring test, a real live regression check
for exactly the mechanism this session's cleanup was told not to break.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/active_node_override_resume_test.py
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
	group_name = f'active_node_override_resume_test_{session_id}'

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

	pr_node_id = load_current_state(group_name).get('active_node_id')
	if not pr_node_id:
		print('not ok - no active_node_id after turn 1 (purchase request never became the active node)')
		sys.exit(1)

	turn2 = send('La fecha requerida es 2026-09-01')
	if turn2 is None:
		print('not ok - turn 2 (supply Required Date) never completed')
		sys.exit(1)

	state_after_turn2 = load_current_state(group_name)
	pr_node_snapshot = next(
		(n for n in (state_after_turn2.get('intention_nodes') or []) if n.get('id') == pr_node_id), None,
	)
	if pr_node_snapshot is None:
		print(f'not ok - could not find the purchase request node ({pr_node_id!r}) in intention_nodes after turn 2')
		sys.exit(1)
	saved_required_date = (pr_node_snapshot.get('form_state') or {}).get('RequriedDate')
	if not saved_required_date:
		print(f'not ok - expected RequriedDate to be set on the PR node after turn 2, got form_state={pr_node_snapshot.get("form_state")!r}')
		sys.exit(1)
	print(f'--- purchase request node after turn 2 (id={pr_node_id!r}) ---')
	print(json.dumps(pr_node_snapshot, indent=2))

	# Deterministically park node A and activate a second node B -- NOT by sending a real
	# side-query turn and relying on Agent: Find to classify it as new_intent, which is
	# separately known to be flaky in exactly this mid-form-interrupt shape (see the
	# module docstring). This isolates the mechanism Phase 2 actually needs to guard:
	# Resolve Override's park/switch logic in intent-manager.json.
	node_b_id = 'test_node_b#1'
	parked_pr_node = {**pr_node_snapshot, 'status': 'paused'}
	node_b = {
		'id': node_b_id, 'parent_id': pr_node_id, 'process_id': 2,
		'process_definition': {'id': 2, 'name': 'List Vendors'},
		'form_state': {'ready': True}, 'status': 'active',
	}
	restore_state(group_name, {
		**state_after_turn2,
		'active_node_id': node_b_id,
		'process_id': 2,
		'process_definition': node_b['process_definition'],
		'form_state': node_b['form_state'],
		'intention_nodes': [parked_pr_node, node_b],
		'paused_node_ids': [pr_node_id],
	})

	state_before_override = load_current_state(group_name)
	print('--- intention_nodes after deterministic setup (before override) ---')
	print(json.dumps(state_before_override.get('intention_nodes'), indent=2))

	failures = []

	# A real click-to-resume always rides along with the user's next typed message (see
	# handleNavigate/handleSend in app/frontend/src/views/chat.vue). "gracias" is used
	# deliberately, not arbitrarily -- Context Enrichment computes pending_kind from the
	# PRE-override active node (node B, form_state.ready=true), so pending_kind is null
	# on this turn regardless of which node the override targets, which per Agent: Find's
	# own systemMessage means only "new_intent" or "general_inquiry" are valid outputs; a
	# content-free acknowledgement is the one message shape reliably classified as
	# general_inquiry (confirmed via workflow/tests/cases/unit/enrich-context.json's own
	# "gracias" fixture) rather than accidentally keyword-matching some real process.
	turn4 = send('gracias', active_node_override=pr_node_id)
	if turn4 is None:
		print('not ok - turn 4 (active_node_override click-to-resume) never completed')
		sys.exit(1)

	finder_child_id = client.get_child_execution_id(turn4, 'Agent: Intent Finder')
	if finder_child_id is not None:
		finder_execution = client.get_execution(finder_child_id)
		find_output = client.get_node_output(finder_execution, 'Agent: Find')
		if find_output is not None:
			print(f"--- Agent: Find raw output on turn 4 --- \n{find_output.get('output')}")

	state_after_turn4 = load_current_state(group_name)
	print('--- state after turn 4 (active_node_override resume) ---')
	print(f"active_node_id: {state_after_turn4.get('active_node_id')!r}")
	print(f"process_id: {state_after_turn4.get('process_id')!r}")
	print(f"form_state: {json.dumps(state_after_turn4.get('form_state'), indent=2)}")

	if state_after_turn4.get('active_node_id') != pr_node_id:
		failures.append(f"expected active_node_id to switch back to the purchase request node {pr_node_id!r}, got {state_after_turn4.get('active_node_id')!r}")

	intention_nodes_after_turn4 = {n['id']: n for n in (state_after_turn4.get('intention_nodes') or [])}
	pr_node_after = intention_nodes_after_turn4.get(pr_node_id)
	if pr_node_after is None:
		failures.append('purchase request node disappeared from intention_nodes after the override resume')
	elif pr_node_after.get('status') != 'active':
		failures.append(f"expected the purchase request node to be reactivated (status=active) after the override resume, got status={pr_node_after.get('status')!r}")

	node_b_after = intention_nodes_after_turn4.get(node_b_id)
	if node_b_after is None:
		failures.append(f'node B ({node_b_id!r}) disappeared from intention_nodes after the override resume')
	elif node_b_after.get('status') != 'paused':
		failures.append(f"expected node B to be parked (status=paused) after switching back to the purchase request, got status={node_b_after.get('status')!r}")
	if state_after_turn4.get('active_node_id') == node_b_id:
		failures.append('expected node B to no longer be the active node after the override resume')

	restored_required_date = (state_after_turn4.get('form_state') or {}).get('DocDate') or (state_after_turn4.get('form_state') or {}).get('RequriedDate')
	if saved_required_date and restored_required_date != saved_required_date:
		failures.append(f'expected the resumed node\'s form_state to carry the Required Date supplied in turn 2 ({saved_required_date!r}), got {restored_required_date!r}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - active_node_override click-to-resume still parks/reactivates correctly after the stack-resume flow removal, session_id={session_id}')


if __name__ == '__main__':
	main()
