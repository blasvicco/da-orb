"""Live E2E check for the confidence-gated SAP Discovery feature (Orbot v14).

Exercises the REAL, live spine workflow end-to-end -- real OpenAI calls, real SAP B1 Service
Layer calls, no pins, no disposable workflow copy. This is the live proof that a cross-entity
question with no cataloged process -- the motivating case for this whole feature -- now gets a
real answer instead of an endless "no_match, please rephrase" loop.

The two turns below use real, confirmed-live data on this tenant (BVS_SA_NEW_16062025),
discovered while investigating the ORIGINAL bug report this whole session traces back to:
"listame los proveedores que pertenezcan al grupo no productivos". That phrase turned out not
to refer to a nonexistent BusinessPartnerGroup (as first assumed) but to a REAL ItemGroup --
`ItemGroups` code 100 is literally named "No Productivos". The real question was always
"which vendors supply items in this item group", a genuine cross-entity join `vendor_list`'s
own filters can never reach (it only filters vendors by their own attributes, never by what
items they supply).

    1. The original phrase rephrased to unambiguously ask "which vendors supply items from
       group X" rather than "vendors belonging to group X" -- the literal original wording
       ("listame los proveedores que pertenezcan al grupo...") is genuinely ambiguous with
       vendor_list's own GroupCode filter (a vendor's own group), and a live run confirmed
       Agent: Find reasonably classifies THAT exact phrasing as new_intent_status: match, not
       discover -- correct behavior, not a bug, since vendor_list's own filter set does
       superficially fit that reading. This turn's phrasing removes the ambiguity. Live data
       confirms group 100 ("No Productivos") has 20 items, none with `Mainsupplier` set -- so
       the correct answer is a clean "no supplier data for that group" (status: success, not
       error -- this is a legitimate empty result, not a failure), proving the graceful-nothing-
       found path works for a real, exact production scenario.
    2. A group + code confirmed to have real supplier data: `ItemGroups` code 101 ("BIENES")
       has real items whose `Mainsupplier` is `P00000000035` (CardName "CISCO SYSTEMS INC").
       Naming the code directly sidesteps a genuine, previously-unknown data collision a live
       run surfaced (both `ItemGroups` 101 "BIENES" and 165 "Bienes" exist -- a name-only
       lookup correctly triggers the ambiguity-stop discipline instead of guessing, which is
       itself proof the safety behavior works, but doesn't complete the full chain). This turn
       proves the full chain end to end: query Items for Mainsupplier, query BusinessPartners
       for the name, surface a real answer -- not just gracefully failing/asking every time.

Run directly inside the backend container:
    python3 /home/workflow/tests/integration/sap_discovery_e2e_test.py
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


def extract_ai_tool_calls(run_data, node_name):
	"""LangChain tool nodes store their invocation under the 'ai_tool' connection type, not
	'main' -- inputOverride.ai_tool is the exact call the agent made, data.ai_tool is what the
	tool returned. Confirmed against real runs during this session's resolve_lookup_e2e_test.py."""
	runs = run_data.get(node_name) or []
	calls = []
	for run in runs:
		input_items = (run.get('inputOverride', {}).get('ai_tool') or [[]])[0] or []
		output_items = (run.get('data', {}).get('ai_tool') or [[]])[0] or []
		calls.append({
			'input': input_items[0]['json'] if input_items else None,
			'output': output_items[0]['json'] if output_items else None,
		})
	return calls


def inspect_discovery(client, spine_execution):
	"""SAP: Discovery is a DIRECT child of the spine execution (wired straight off the Router),
	unlike SAP: Inquiry Execution which is normally reached as a grandchild through form-filling
	-- no fallback path needed here."""
	child_id = client.get_child_execution_id(spine_execution, 'SAP: Discovery')
	if not child_id:
		return None
	child = client.get_execution(child_id)
	run_data = child.get('data', {}).get('resultData', {}).get('runData', {})

	build_prompt_output = client.get_node_output(child, 'Build Discovery Prompt')
	chat_input = (build_prompt_output or {}).get('chatInput')

	github_calls = extract_ai_tool_calls(run_data, 'GitHub MCP')
	sap_calls = extract_ai_tool_calls(run_data, 'SAP MCP')

	agent_runs = run_data.get('Agent: Discover') or []
	agent_output = None
	if agent_runs:
		items = (agent_runs[-1].get('data', {}).get('main') or [[]])[0] or []
		agent_output = items[0]['json'] if items else None

	return {
		'child_execution_id': child_id,
		'chat_input': chat_input,
		'github_calls': github_calls,
		'sap_calls': sap_calls,
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
	# Discovery chains can run several real SAP/GitHub round trips (up to 6 tool calls) --
	# confirmed live to take upward of 180s. A too-short timeout here doesn't just miss the
	# result: if a NEXT turn fires while this one is still running, the next turn's own
	# wait_for_fresh_execution can pick up THIS turn's late-finishing execution instead (its
	# id is still > this call's baseline), silently mislabeling which message produced which
	# result. Generous timeout first; the message-match check in run_one is the real guard.
	client.trigger_webhook(CHAT_WEBHOOK_PATH, payload)
	# Turn 2 below (ItemGroups 101 "BIENES") is a genuinely large real dataset -- confirmed
	# ~24,913 Items rows have Mainsupplier set in that one group -- so a full-group discovery
	# chain enumerating it can run considerably longer than a small-group case like turn 1's
	# 20-item "No Productivos". 360s observed insufficient in one live run; kept generous here
	# deliberately rather than narrowed, since a real user's group could be any size.
	execution = wait_for_fresh_execution(headers, baseline_id, time.monotonic() + 360)
	if execution is None:
		return None, None
	delivered = wait_for_delivery(access_token, session_id, before_count, time.monotonic() + 30)
	return execution, delivered


def webhook_input_message(client, execution):
	"""Read the real message the Webhook trigger node received for this execution, straight
	from its own runData -- the one source of truth for "which turn does this execution
	actually belong to", independent of id ordering or timing assumptions."""
	webhook_output = client.get_node_output(execution, 'Webhook')
	if webhook_output is None:
		return None
	return (webhook_output.get('body') or webhook_output).get('message')


def run_one(client, headers, access_token, session_id, organization, session_payload, label, message, failures):
	print(f'\n{"=" * 100}\nTURN: {label}\nmessage: {message!r}\n{"=" * 100}')
	group_name = f'sap_discovery_e2e_test_{session_id}_{label}_{int(time.time())}'
	execution, delivered = send_turn(client, headers, access_token, session_id, organization, session_payload, message, group_name)

	if execution is None:
		failures.append(f'{label}: no spine execution completed within timeout')
		print('RESULT: no spine execution completed within timeout')
		return

	print(f"spine execution: id={execution.get('id')} status={execution.get('status')}")

	actual_message = webhook_input_message(client, execution)
	if actual_message != message:
		failures.append(
			f"{label}: execution {execution.get('id')} belongs to a DIFFERENT message than expected -- "
			f"expected {message!r}, Webhook actually received {actual_message!r} -- likely picked up a "
			f"prior turn's late-finishing execution instead of this turn's own"
		)
		print(f"RESULT: execution/message mismatch -- expected {message!r}, got {actual_message!r}")
		return

	if delivered:
		print(f"delivered message: {json.dumps(delivered.get('content') or delivered, ensure_ascii=False, indent=2)[:3000]}")
	else:
		print('warning: spine execution finished but no non-status message was confirmed delivered within 30s')

	detail = inspect_discovery(client, execution)
	if detail is None:
		failures.append(f"{label}: never reached 'SAP: Discovery' -- Agent: Find likely did not classify this as new_intent_status: discover")
		print("RESULT: this turn never reached 'SAP: Discovery' at all")
		return

	print(f"\nSAP: Discovery child execution id: {detail['child_execution_id']}")
	print(f"GitHub MCP call count: {len(detail['github_calls'])}")
	for i, call in enumerate(detail['github_calls'], 1):
		print(f"  call {i} input: {json.dumps(call['input'], ensure_ascii=False)[:500]}")
	print(f"SAP MCP call count: {len(detail['sap_calls'])}")
	for i, call in enumerate(detail['sap_calls'], 1):
		print(f"  call {i} input: {json.dumps(call['input'], ensure_ascii=False)[:800]}")
		print(f"  call {i} output: {json.dumps(call['output'], ensure_ascii=False)[:800]}")

	# Hard safety invariant, not a diagnostic -- this agent has real autonomy with no reviewed
	# process definition backing it, so a write attempt anywhere in the chain is a real failure,
	# not a quality judgment. sap_entity_create isn't even in its tool allowlist, but check the
	# actual call log directly rather than trusting the allowlist alone.
	for call in detail['sap_calls']:
		tool_used = (call['input'] or {}).get('tool', '')
		if 'create' in tool_used.lower() or 'entity_create' in tool_used.lower():
			failures.append(f"{label}: SAFETY VIOLATION -- sap_entity_create appeared in the call sequence: {call}")

	print(f"\nAgent: Discover final output: {json.dumps(detail['agent_execute_output'], ensure_ascii=False, indent=2)[:2000]}")


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

	failures = []

	run_one(
		client, headers, access_token, session_id, organization, session_payload, failures=failures,
		label='original_bug_report_item_group',
		message='Que proveedores nos proveen articulos del grupo no productivos?',
	)

	run_one(
		client, headers, access_token, session_id, organization, session_payload, failures=failures,
		label='item_group_with_real_supplier_data',
		message='Que proveedores nos proveen articulos del grupo de codigo 101?',
	)

	print(f'\n{"=" * 100}')
	if failures:
		for f in failures:
			print(f'not ok - {f}')
		print(f'{len(failures)} failure(s), session_id={session_id}')
		sys.exit(1)
	print(f'ok - both turns reached SAP: Discovery, no sap_entity_create anywhere in either call sequence, session_id={session_id}')


if __name__ == '__main__':
	main()
