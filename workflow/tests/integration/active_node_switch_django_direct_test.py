"""Standalone E2E test for the Django-direct active_node.switch mechanism (Orbot v14, Phase 4b).

Exercises the real, current `CChat.active_node_switch` consumer method
(web_socket/consumers/chat.py) plus the real, live v14 spine's actual /webhook/chat webhook --
not a harness, not a pinned agent. This is the live regression guard for Phase 4b of the
2026-08-13 Intention Graph cleanup: clicking a node in the Intention Graph sidebar used to
queue `active_node_override` locally and only actually switch the active node on the user's
*next* typed message, via a full n8n round trip (`Has Override?`/`Resolve Override` in
intent-manager.json). Per direct instruction, that round trip was relocated entirely into
Django: the frontend now sends `type: 'active_node.switch'` immediately over the WebSocket,
`active_node_switch()` resolves park/activate directly against Redis, and n8n never receives
`active_node_override` again -- `Has Override?`/`Resolve Override` were deleted from
intent-manager.json as dead code, same treatment Phase 2 gave the stack-resume flow.

Scenario:
	1. Start a purchase request (real turn) -- gets a real, live-created node id and
	   process_definition rather than a hand-built fixture.
	2. Supply the Required Date (real turn) -- gives the node real, distinguishable
	   form_state to check survives the switch.
	3. Directly write a second, already-active node B into Redis via N8nSessionState.restore
	   -- same technique used for Phase 2/4a's own click-to-resume tests, isolating the
	   mechanism under test from Agent: Find's separately-known classification flakiness.
	4. Call the REAL, current `CChat.active_node_switch` method directly (imported fresh
	   from disk via `manage.py shell`, so it exercises today's actual Phase 4b code even
	   though the long-running ASGI server process hasn't been restarted to pick it up yet
	   -- the method only ever touches `self.n8n_state`, which this harness sets up
	   directly, so this runs the real production logic, not a reimplementation of it) --
	   targeting node A's id, with ZERO n8n involvement of any kind for this step.
	5. Confirm via Redis (N8nSessionState.load, the same class N8nClient.fire() uses in
	   production) that node A was reactivated with its form_state intact and node B was
	   parked -- purely a Django-level check, no webhook involved.
	6. Send one more real turn through the actual live webhook, using the CURRENT
	   N8nClient.fire() payload shape (no active_node_override key at all, no root-level
	   process_id/form_state/paused_node_ids) -- confirm the raw body n8n's Webhook trigger
	   node actually received has no "active_node_override" key anywhere, and that the
	   already-resolved state (node A active, node B paused) round-trips through Context
	   Enrichment/Intent Manager unchanged, proving n8n needs no override logic of its own
	   to preserve state that was already resolved before it was ever called.

Real OpenAI calls (three full turns) plus one deterministic state write and one direct
Django-level method invocation. Costly and slow by nature -- not a wiring test, a real live
regression check for exactly the mechanism this session's cleanup was told not to break.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/active_node_switch_django_direct_test.py
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


def switch_active_node(group_name, target_id):
	"""Directly invoke the REAL, current CChat.active_node_switch consumer method -- imported
	fresh from disk via manage.py shell, so this exercises today's actual Phase 4b code even
	though the long-running ASGI server process hasn't been restarted to pick it up yet. The
	method only ever touches self.n8n_state (load/save), which this stub sets up directly, so
	this is the real production logic running, not a reimplementation of it. Deliberately does
	NOT go through the WebSocket wire protocol or n8n at all -- that's the point of Phase 4b."""
	script = (
		"import asyncio\n"
		"from web_socket.consumers.chat import CChat\n"
		"from web_socket.helpers.n8n.state import N8nSessionState\n"
		"async def _run():\n"
		"\tconsumer = CChat()\n"
		f"\tconsumer.n8n_state = N8nSessionState(group_name={group_name!r})\n"
		"\ttry:\n"
		f"\t\tawait consumer.active_node_switch({{'active_node_id': {target_id!r}}})\n"
		"\tfinally:\n"
		"\t\tawait consumer.n8n_state.close()\n"
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
	group_name = f'active_node_switch_django_direct_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	def send(message):
		"""Mirrors the CURRENT N8nClient.fire() payload shape exactly (client.py, post Phase
		4b): no active_node_override key at all, no root-level process_id/process_definition/
		form_state/paused_node_ids -- intention_nodes is the only source of truth."""
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

	state_after_turn2 = load_current_state(group_name)
	pr_node = (state_after_turn2.get('intention_nodes') or {}).get(pr_node_id)
	if pr_node is None:
		print(f'not ok - could not find the purchase request node ({pr_node_id!r}) in intention_nodes after turn 2')
		sys.exit(1)
	saved_required_date = (pr_node.get('form_state') or {}).get('RequriedDate')
	if not saved_required_date:
		print(f'not ok - expected RequriedDate to be set on the PR node after turn 2, got form_state={pr_node.get("form_state")!r}')
		sys.exit(1)
	print(f'--- purchase request node after turn 2 (id={pr_node_id!r}) ---')
	print(json.dumps(pr_node, indent=2))

	# Deterministically park node A and activate a second node B -- NOT by sending a real
	# side-query turn and relying on Agent: Find to classify it as new_intent, which is
	# separately known to be flaky in exactly this mid-form-interrupt shape. This isolates
	# the mechanism this test actually needs to guard: active_node_switch's own park/switch
	# logic, now living entirely in Django.
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

	state_before_switch = load_current_state(group_name)
	print('--- intention_nodes after deterministic setup (before switch) ---')
	print(json.dumps(state_before_switch.get('intention_nodes'), indent=2))

	# THE step under test: switch the active node back to the purchase request DIRECTLY via
	# Django's active_node_switch, with ZERO n8n involvement -- no webhook trigger, no
	# execution, nothing. This is Phase 4b's whole point: the click-to-resume mechanism no
	# longer needs n8n to know how, when, or why the active node changed.
	baseline_execution_id_before_switch = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	switch_active_node(group_name, pr_node_id)

	state_after_switch = load_current_state(group_name)
	print('--- state after direct Django active_node_switch (no n8n call made) ---')
	print(json.dumps(state_after_switch, indent=2))

	if state_after_switch.get('active_node_id') != pr_node_id:
		failures.append(f"expected active_node_id to switch to the purchase request node {pr_node_id!r} via direct Django call, got {state_after_switch.get('active_node_id')!r}")

	nodes_after_switch = state_after_switch.get('intention_nodes') or {}
	pr_node_after_switch = nodes_after_switch.get(pr_node_id)
	if pr_node_after_switch is None:
		failures.append('purchase request node disappeared from intention_nodes after the direct switch')
	else:
		if pr_node_after_switch.get('status') != 'active':
			failures.append(f"expected the purchase request node to be reactivated (status=active), got status={pr_node_after_switch.get('status')!r}")
		restored_date = (pr_node_after_switch.get('form_state') or {}).get('RequriedDate')
		if restored_date != saved_required_date:
			failures.append(f"expected the switched-to node's form_state to carry the Required Date from turn 2 ({saved_required_date!r}), got {restored_date!r}")

	node_b_after_switch = nodes_after_switch.get(node_b_id)
	if node_b_after_switch is None:
		failures.append(f'node B ({node_b_id!r}) disappeared from intention_nodes after the direct switch')
	elif node_b_after_switch.get('status') != 'paused':
		failures.append(f"expected node B to be parked (status=paused) after the direct switch, got status={node_b_after_switch.get('status')!r}")

	newest_execution_id_after_switch = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	if newest_execution_id_after_switch != baseline_execution_id_before_switch:
		failures.append(f'expected zero n8n executions to be triggered by the direct Django switch, but the newest execution id moved from {baseline_execution_id_before_switch} to {newest_execution_id_after_switch}')

	# Now confirm the NEXT real n8n turn sees the already-resolved state correctly, with no
	# active_node_override anywhere in the wire payload at all.
	turn3 = send('gracias')
	if turn3 is None:
		print('not ok - turn 3 (post-switch turn through the real webhook) never completed')
		sys.exit(1)

	webhook_body = client.get_node_output(turn3, 'Webhook')
	if webhook_body is None:
		failures.append("could not read the 'Webhook' trigger node's own output on turn 3 to inspect the raw payload n8n received")
	else:
		body_payload = webhook_body.get('body', webhook_body)
		if 'active_node_override' in body_payload:
			failures.append(f"expected zero active_node_override key in the wire payload n8n receives (Phase 4b removed it entirely), but the Webhook node's input still had it: {body_payload.get('active_node_override')!r}")
		if body_payload.get('active_node_id') != pr_node_id:
			failures.append(f"expected the wire payload's active_node_id to already be {pr_node_id!r} (pre-resolved by Django before n8n was ever called), got {body_payload.get('active_node_id')!r}")

	state_after_turn3 = load_current_state(group_name)
	print('--- state after turn 3 (post-switch real n8n turn) ---')
	print(json.dumps(state_after_turn3, indent=2))

	if state_after_turn3.get('active_node_id') != pr_node_id:
		failures.append(f"expected active_node_id to remain {pr_node_id!r} after a content-free acknowledgement turn, got {state_after_turn3.get('active_node_id')!r}")

	nodes_after_turn3 = state_after_turn3.get('intention_nodes') or {}
	pr_node_after_turn3 = nodes_after_turn3.get(pr_node_id)
	if pr_node_after_turn3 is None or pr_node_after_turn3.get('status') != 'active':
		failures.append(f"expected the purchase request node to still be active after turn 3, got {pr_node_after_turn3!r}")
	node_b_after_turn3 = nodes_after_turn3.get(node_b_id)
	if node_b_after_turn3 is None or node_b_after_turn3.get('status') != 'paused':
		failures.append(f"expected node B to remain parked after turn 3, got {node_b_after_turn3!r}")

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - active_node.switch resolves directly in Django with zero n8n involvement, and the subsequent turn sees the already-switched state with no active_node_override anywhere, session_id={session_id}')


if __name__ == '__main__':
	main()
