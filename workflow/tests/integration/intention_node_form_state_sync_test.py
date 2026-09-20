"""Standalone E2E test for intention_nodes[i].form_state staying live turn-to-turn (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent. This is the confirmed bug fixed on 2026-08-13: a node's form_state only got
mirrored from the root-level "working copy" into its own intention_nodes entry at
park/resume time (Resolve Override/Park Current Intent/Resolve Stack Resume,
intent-manager.json) -- never on the turns in between while it stayed active. Concrete
consequence: Prompt: Intention Focus (agent-intent-finder.json) computes each node's
missing_required_fields straight off node.form_state, so it saw an active node's progress
as frozen at creation for as long as it stayed active.

Scenario:
	1. Start a purchase request (node stays 'active', nothing parks it).
	2. Supply ONLY the header's Required Date -- leaves every line-item-level required field
	   (Item Code, Quantity, etc.) still missing, so this isolates exactly one field flipping
	   from missing to filled.
	3. Send an unrelated message (a vendor lookup, proven safe by an earlier test this
	   session) purely to trigger a fresh Agent: Intent Finder run and inspect what
	   Prompt: Intention Focus computed for the still-active PR node this same turn.
	4. Assert "Required Date" is no longer in that node's missing_required_fields --
	   proving intention_nodes[0].form_state picked up the turn-2 value without the node
	   ever being parked.

Real OpenAI calls (three full turns). Costly and slow by nature -- not a wiring test, a
real live regression check for exactly the failure mode this was written to catch.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/intention_node_form_state_sync_test.py
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
	# manage.py shell may print a "N objects imported automatically" banner line first --
	# the actual JSON is always the last line of stdout.
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
	group_name = f'form_state_sync_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	def send(message):
		# Replicate N8nClient.fire()'s exact payload shape (web_socket/helpers/n8n/client.py)
		# -- a real user's turn always goes through fire(), which loads current Redis state
		# and threads it into the webhook body. Triggering the raw webhook without this step
		# is not a faithful reproduction of a real turn; it's an isolated, state-less probe.
		current = load_current_state(group_name)
		payload = {
			'message': message,
			'expertise_level': 3,
			'group_name': group_name,
			'organization': organization,
			'session': session_payload,
			'session_id': session_id,
			'active_node_id': current.get('active_node_id'),
			'awaiting_stack_resume': current.get('awaiting_stack_resume', False),
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

	turn2 = send('La fecha requerida es 2026-09-01')
	if turn2 is None:
		print('not ok - turn 2 (supply Required Date only) never completed')
		sys.exit(1)

	turn3 = send(
		'Podes listarme los proveedores que esten asociados al grupo codigo 100 '
		'(No productivos), cuya moneda sea ARS y que el nombre no contenga "NO USAR".'
	)
	if turn3 is None:
		print('not ok - turn 3 (unrelated side query, to trigger a fresh Intention Focus run) never completed')
		sys.exit(1)

	failures = []

	finder_child_id = client.get_child_execution_id(turn3, 'Agent: Intent Finder')
	if finder_child_id is None:
		print('not ok - Agent: Intent Finder never ran on turn 3')
		sys.exit(1)
	finder_execution = client.get_execution(finder_child_id)

	prompt_focus_output = client.get_node_output(finder_execution, 'Prompt: Intention Focus')
	if prompt_focus_output is None:
		failures.append('Prompt: Intention Focus never ran on turn 3')
	else:
		chat_input = prompt_focus_output.get('chatInput') or ''
		print('--- INTENTION TREE seen by Agent: Intention Focus on turn 3 ---')
		tree_start = chat_input.find('```json')
		print(chat_input[tree_start:tree_start + 600] if tree_start != -1 else chat_input)
		if '"missing_required_fields"' in chat_input:
			# Isolate the missing_required_fields array's own content -- checking for
			# "Required Date" anywhere in chat_input would be wrong both ways: it could
			# appear elsewhere in the prompt for unrelated reasons, and (the actual bug
			# caught here first) a SUCCESSFUL fix means "Required Date" legitimately
			# doesn't appear ANYWHERE once it's no longer missing, so gating the whole
			# check on its presence guarantees a false failure on success.
			import re
			match = re.search(r'"missing_required_fields":\s*\[(.*?)\]', chat_input, re.DOTALL)
			missing_list = match.group(1) if match else ''
			print('--- missing_required_fields content ---')
			print(missing_list)
			if 'Required Date' in missing_list:
				failures.append(
					f'expected "Required Date" to be gone from missing_required_fields after turn 2 supplied it, '
					f'but it is still listed -- intention_nodes[i].form_state did not pick up the turn-2 value: {missing_list!r}'
				)
			if not any(f in missing_list for f in ('Item Code', 'Quantity', 'Sector')):
				failures.append(
					f'expected the still-unfilled item-level required fields to remain listed (proving this is a '
					f'real, populated tree, not an accidentally-empty one that would trivially pass), got: {missing_list!r}'
				)
		else:
			failures.append(f'could not find missing_required_fields in the INTENTION TREE prompt: {chat_input[:300]!r}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - intention_nodes[i].form_state stayed live turn-to-turn without parking, session_id={session_id}')


if __name__ == '__main__':
	main()
