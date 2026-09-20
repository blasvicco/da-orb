"""Standalone E2E test for GET-type process multi-operator query filters (Orbot v14).

Exercises the real, live v14 spine's actual /webhook/chat webhook -- not a harness, not a
pinned agent -- with a single real message that specifies three filters, one of them a
negation ("el nombre no contenga X"). This is the exact scenario that broke live, twice, on
2026-08-12: Agent: Form silently confirmed with an empty form_state, discarding every filter
the user gave it. Confirms:
  1. Agent: Form actually extracts all three filter values into form_state, with a negated
     operator recorded for the name exclusion.
  2. The OData filter string Build Execution Prompt actually builds combines all three with
     AND (the user's message joins them with "y"/"y") and correctly negates the name clause.

Real OpenAI calls, real SAP MCP query (read-only GET against BusinessPartners, no data
created or modified). Costly and slow by nature (~10-30s, real LLM latency) -- not a wiring
test, a real live regression check for exactly the failure mode this was written to catch.

Run directly inside the backend container:
	python3 /home/workflow/tests/integration/vendor_list_filter_test.py
"""
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
NEGATED_OPERATORS = ('not_contains', 'not_startswith', 'not_endswith')


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
	group_name = f'vendor_filter_test_{session_id}'

	client = N8nClient()
	headers = {'X-N8N-API-KEY': os.environ['N8N_API_KEY']}

	baseline_id = client.get_latest_execution_id(SPINE_WORKFLOW_ID)
	client.trigger_webhook(CHAT_WEBHOOK_PATH, {
		'message': (
			'Podes listarme los provedorees que esten asociados al grupo codigo 100 '
			'(No productivos), cuya moneda sea ARS y que el nombre no contenga "NO USAR".'
		),
		'expertise_level': 3,
		'group_name': group_name,
		'organization': organization,
		'session': session_payload,
		'session_id': None,
	})

	print('Triggered -- polling for the execution to complete...')
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 120)
	if execution is None:
		print('not ok - no execution completed within the deadline')
		sys.exit(1)

	failures = []

	form_filling_child_id = client.get_child_execution_id(execution, 'SAP: Process Form Filling')
	if form_filling_child_id is None:
		print('not ok - SAP: Process Form Filling never ran (classification or routing failure)')
		sys.exit(1)
	form_filling_execution = client.get_execution(form_filling_child_id)

	agent_form_output = client.get_node_output(form_filling_execution, 'Agent: Form')
	if agent_form_output is None:
		failures.append('Agent: Form never ran')
	else:
		fs = agent_form_output.get('form_state') or {}
		print('--- Agent: Form form_state ---')
		print(fs)
		if fs.get('GroupCode') != 100:
			failures.append(f'expected form_state.GroupCode == 100, got {fs.get("GroupCode")!r}')
		if fs.get('Currency') != 'ARS':
			failures.append(f'expected form_state.Currency == "ARS", got {fs.get("Currency")!r}')
		if 'NO USAR' not in str(fs.get('CardName') or ''):
			failures.append(f'expected form_state.CardName to reference "NO USAR", got {fs.get("CardName")!r}')
		if fs.get('CardName_operator') not in NEGATED_OPERATORS:
			failures.append(f'expected a negated CardName_operator, got {fs.get("CardName_operator")!r}')

	inquiry_execution_child_id = client.get_child_execution_id(form_filling_execution, 'Execute Workflow: SAP Inquiry Execution')
	if inquiry_execution_child_id is None:
		failures.append('SAP: Inquiry Execution never ran')
	else:
		inquiry_execution = client.get_execution(inquiry_execution_child_id)
		prompt_output = client.get_node_output(inquiry_execution, 'Build Execution Prompt')
		if prompt_output is None:
			failures.append('Build Execution Prompt never ran')
		else:
			chat_input = prompt_output.get('chatInput') or ''
			filters_line = next((line for line in chat_input.split('\n') if line.startswith('PRE-BUILT FILTERS')), '')
			print('--- PRE-BUILT FILTERS line ---')
			print(filters_line)
			if "CardType eq 'cSupplier'" not in filters_line:
				failures.append(f'expected the mandatory default_filters clause CardType eq \'cSupplier\' in the built filter (2026-08-13 regression: default_filters were never applied, so vendor_list returned customers and leads too), got: {filters_line}')
			if 'not' not in filters_line or 'CardName' not in filters_line:
				failures.append(f'expected a negated CardName clause in the built filter, got: {filters_line}')
			if 'GroupCode eq 100' not in filters_line:
				failures.append(f'expected "GroupCode eq 100" in the built filter, got: {filters_line}')
			if 'Currency' not in filters_line:
				failures.append(f'expected a Currency clause in the built filter, got: {filters_line}')
			if ' and ' not in filters_line:
				failures.append(f'expected all filters joined with AND (match_all, from the "y"/"y" in the message), got: {filters_line}')

	if failures:
		for failure in failures:
			print(f'not ok - {failure}')
		sys.exit(1)

	print(f'ok - GET-query multi-operator filters (group + currency + negated name) extracted and built correctly, session_id={session_id}')


if __name__ == '__main__':
	main()
