"""Standalone E2E test for a side-query arriving mid-form-fill (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent -- with a two-turn conversation: (1) start a purchase request, leaving it
mid-form with required fields still missing, then (2) ask to list vendors, worded exactly
the way a user would when looking up a value for one of those still-open fields. This is
the exact scenario that broke live on 2026-08-13: Agent: Find classified turn 2 as
"pending_reply"/"form_fill" (a value for the still-open purchase request) instead of
"new_intent" (a distinct SAP lookup), so the vendor-list request was silently swallowed
and the bot just re-asked for the purchase request's own missing fields.

Confirms Agent: Find defers to Agent: Intention Focus's read of "the user is pursuing
something else" instead of independently re-deriving pending_reply vs new_intent via its
own separate heuristics, per the fix landed the same day.

Real OpenAI calls (two full turns). Costly and slow by nature -- not a wiring test, a real
live regression check for exactly the failure mode this was written to catch.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/vendor_lookup_during_form_fill_test.py
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
	prior-turn state at all, unlike a real user's turn, which always goes through fire().
	REGRESSION (2026-08-13): without this, turn 2 ran against an empty intention_nodes/
	active_node_id -- any apparent continuity came from Agent: Intention Focus's own
	LangChain memory buffer, not the structured graph state this system is actually
	designed around, which is not a faithful test of the real turn-to-turn behavior."""
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
	"""Same endpoint the frontend polls/subscribes to -- the real signal a turn is fully
	delivered and persisted (n8n_callback -> MChatMessage.objects.create), not just that
	n8n's own execution reached a terminal status. A message can still be in flight through
	the async callback for a moment after n8n reports "success"."""
	response = requests.get(
		'http://localhost/api/v1/chat/messages/',
		headers={'Host': DJANGO_HOST, 'Authorization': f'Bearer {access_token}'},
		params={'session_id': session_id},
		timeout=15,
	)
	response.raise_for_status()
	return response.json()


def wait_for_delivery(access_token, session_id, before_count, deadline):
	"""Poll until a new non-status message is actually persisted for this session -- confirms
	the per-group_name in-flight lock (_release_and_refire) has been released, so the next
	send() won't get silently queued behind a callback that hasn't finished yet."""
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
	group_name = f'vendor_lookup_mid_form_test_{session_id}'

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
		# n8n reporting the execution as terminal doesn't guarantee the async n8n_callback
		# (which persists the message and releases the per-group_name in-flight lock) has
		# finished yet -- wait for the actual delivered message before letting the caller
		# send the next turn, or that next trigger can get silently queued behind this one.
		delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
		if delivered is None:
			print('warning: n8n execution finished but no message was confirmed delivered/persisted within 30s')
		return execution

	turn1 = send('Quiero crear una solicitud de compra')
	if turn1 is None:
		print('not ok - turn 1 (start purchase request) never completed')
		sys.exit(1)

	turn2 = send(
		'Podes listarme los proveedores que esten asociados al grupo codigo 100 '
		'(No productivos), cuya moneda sea ARS y que el nombre no contenga "NO USAR".'
	)
	if turn2 is None:
		print('not ok - turn 2 (vendor lookup) never completed')
		sys.exit(1)

	failures = []

	finder_child_id = client.get_child_execution_id(turn2, 'Agent: Intent Finder')
	if finder_child_id is None:
		print('not ok - Agent: Intent Finder never ran on turn 2')
		sys.exit(1)
	finder_execution = client.get_execution(finder_child_id)

	find_output = client.get_node_output(finder_execution, 'Agent: Find')
	if find_output is None:
		failures.append('Agent: Find never ran')
	else:
		raw = find_output.get('output') or ''
		print('--- Agent: Find raw output ---')
		print(raw)
		if '"status":"pending_reply"' in raw.replace(' ', '') or '"status": "pending_reply"' in raw:
			failures.append(f'expected "new_intent", got a pending_reply classification (the exact regression this test guards): {raw}')
		if '"status":"new_intent"' not in raw.replace(' ', '') and '"status": "new_intent"' not in raw:
			failures.append(f'expected Agent: Find to classify turn 2 as new_intent, got: {raw}')

	# sap_form_filling is the correct route_key for ANY new_intent/match (GET or POST) --
	# it's the universal process dispatcher, which itself calls SAP: Inquiry Execution
	# internally once it recognizes a GET-type process needs no field-by-field filling.
	# The real signal that the vendor lookup actually ran (not just got classified
	# correctly) is checked below via the Form Filling child's own execution.
	route_key = client.get_node_output(finder_execution, 'Compute Route Key')
	if route_key is not None:
		print('--- route_key ---')
		print(route_key.get('route_key'))

	form_filling_child_id = client.get_child_execution_id(turn2, 'SAP: Process Form Filling')
	if form_filling_child_id is None:
		failures.append('SAP: Process Form Filling never ran on turn 2')
	else:
		ff_execution = client.get_execution(form_filling_child_id)
		ff_run_data = ff_execution.get('data', {}).get('resultData', {}).get('runData', {})
		if 'Execute Workflow: SAP Inquiry Execution' not in ff_run_data:
			failures.append('SAP: Inquiry Execution never ran inside the form-filling dispatch -- the vendor lookup was classified correctly but never actually executed')
		outcome = client.get_node_output(ff_execution, 'Compute Form Outcome')
		if outcome is not None:
			bot_message = outcome.get('message') or ''
			print('--- final bot message ---')
			print(bot_message)
			if 'proveedor' not in bot_message.lower() and 'vendor' not in bot_message.lower():
				failures.append(f'expected the final message to reference vendors/proveedores (confirming the lookup ran, not a re-prompt for purchase request fields), got: {bot_message}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - vendor lookup mid-form-fill correctly classified as new_intent, session_id={session_id}')


if __name__ == '__main__':
	main()
