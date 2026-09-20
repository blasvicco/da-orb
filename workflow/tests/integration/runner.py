"""Entry point: python runner.py <workflow.json>

Runs each cases/integration/*.json suite against a disposable copy of the target workflow
created (and torn down) in n8n for that suite alone — the live workflow already deployed in
n8n is never touched. See engine/workflow_loader.py for why pinning works by node
substitution rather than n8n's pinData (which is ignored on webhook-triggered executions).
"""
import json
import sys
import time
import uuid
from pathlib import Path

from engine.n8n_client import N8nClient
from engine.workflow_loader import WorkflowLoader

# Throttle between cases: confirmed live that firing many executions back-to-back can
# overwhelm n8n's external JS Task Runner (it starts missing task-offer acceptance windows,
# then fails its own heartbeat and restarts) -- especially now that some paths (e.g. the error
# path, since Stage 8 moved Output & Delivery behind a nested sub-workflow call the spine-level
# harness can no longer pin around) always exercise output-delivery.json's own recursive
# n8n-nodes-base.n8n calls back into n8n's REST API. A small pause between cases keeps
# sustained load well under whatever threshold triggers that spiral.
CASE_THROTTLE_SECONDS = 3

CASE_DIR = Path(__file__).parent.parent / 'cases' / 'integration'
# Sub-workflow suites (executeWorkflowTrigger, no webhook of their own) live in their own
# directory rather than mixed into CASE_DIR — a spine suite and a sub-workflow suite assert on
# disjoint node sets and can't both be run against whatever single workflow path was loaded.
SUBWORKFLOW_CASE_DIR = CASE_DIR / 'subworkflows'


def get_field(data, dotted_key):
	"""Resolve a dotted field path (e.g. "state.process_id") against a node's output json."""
	value = data
	for part in dotted_key.split('.'):
		value = (value or {}).get(part)
	return value


def run_case(client, loader, workflow_id, webhook_path, case):
	"""Apply the case's pins, trigger the workflow, and assert on the target node's output."""
	definition = loader.build_test_definition(webhook_path, case.get('pins', {}))
	client.update_workflow(workflow_id, definition)
	baseline_id = client.get_latest_execution_id(workflow_id)
	client.trigger_webhook(webhook_path, case['input'])
	execution = client.wait_for_execution(workflow_id, after_id=baseline_id)
	node_output = client.get_node_output(execution, case['assert']['node'])
	if node_output is None:
		return [f'node "{case["assert"]["node"]}" never ran (execution status={execution.get("status")})']
	failures = []
	for field, expected in case['assert']['fields'].items():
		actual = get_field(node_output, field)
		if actual != expected:
			failures.append(f'{field}: expected {expected!r}, got {actual!r}')
	return failures


def run_suite(client, loader, suite_path):
	"""Create one disposable workflow for the whole suite file, reused across its cases."""
	suite = json.loads(suite_path.read_text(encoding='utf-8'))
	webhook_path = f'test-{suite["path"]}-{uuid.uuid4().hex[:8]}'
	definition = loader.build_test_definition(webhook_path, {})
	workflow_id = client.create_workflow(definition)['id']
	results = []
	try:
		client.activate_workflow(workflow_id)
		for case in suite['cases']:
			try:
				failures = run_case(client, loader, workflow_id, webhook_path, case)
			except Exception as exc:  # keep going so one broken case doesn't hide the rest
				failures = [f'error: {exc}']
			results.append((f'{suite["path"]}: {case["description"]}', failures))
			time.sleep(CASE_THROTTLE_SECONDS)
	finally:
		client.cleanup_workflow(workflow_id)
	return results


def build_harness_definition(webhook_path, target_workflow_id, skip_unwrap=False):
	"""Webhook -> Unwrap Body -> Execute Workflow[target_workflow_id].

	A sub-workflow triggered by executeWorkflowTrigger has no webhook of its own — it's only
	ever reached via an Execute Workflow node — so this small generic harness stands in for
	whatever spine node would normally call it. "Unwrap Body" mirrors what every real caller
	already does before reaching an Execute Workflow node (e.g. context-enrichment.json's own
	Enrich Context strips the webhook's {headers,params,query,body} envelope down to a flat
	object for every node downstream of it): without it, the sub-workflow's trigger would
	receive the raw webhook envelope instead of the flat contract fields (database_path,
	github_api_base, ...) its nodes actually expect on $json.

	skip_unwrap=True wires Webhook straight to Execute Workflow instead. context-enrichment.json
	is the one sub-workflow this doesn't hold for: it's the unwrapper itself, called directly
	off spine.json's raw Webhook node with no flattening step in between (confirmed live: the
	generic two-step harness caused Enrich Context's own `$input.first().json.body` read to
	throw on `undefined`, since the harness had already stripped `.body` away a step earlier).
	"""
	webhook_id, unwrap_id, execute_id = (str(uuid.uuid4()) for _ in range(3))
	nodes = [
		{
			'parameters': {'httpMethod': 'POST', 'path': webhook_path, 'options': {}},
			'type': 'n8n-nodes-base.webhook',
			'typeVersion': 2.1,
			'position': [0, 0],
			'id': webhook_id,
			'name': 'Webhook',
			'webhookId': webhook_id,
		},
	]
	connections = {}
	if skip_unwrap:
		nodes.append({
			'parameters': {'workflowId': {'__rl': True, 'value': target_workflow_id, 'mode': 'id'}, 'options': {}},
			'type': 'n8n-nodes-base.executeWorkflow',
			'typeVersion': 1.2,
			'position': [200, 0],
			'id': execute_id,
			'name': 'Execute Workflow',
		})
		connections['Webhook'] = {'main': [[{'node': 'Execute Workflow', 'type': 'main', 'index': 0}]]}
	else:
		nodes.append({
			'parameters': {'jsCode': 'return [{ json: $json.body }];'},
			'type': 'n8n-nodes-base.code',
			'typeVersion': 2,
			'position': [200, 0],
			'id': unwrap_id,
			'name': 'Unwrap Body',
		})
		nodes.append({
			'parameters': {'workflowId': {'__rl': True, 'value': target_workflow_id, 'mode': 'id'}, 'options': {}},
			'type': 'n8n-nodes-base.executeWorkflow',
			'typeVersion': 1.2,
			'position': [400, 0],
			'id': execute_id,
			'name': 'Execute Workflow',
		})
		connections['Webhook'] = {'main': [[{'node': 'Unwrap Body', 'type': 'main', 'index': 0}]]}
		connections['Unwrap Body'] = {'main': [[{'node': 'Execute Workflow', 'type': 'main', 'index': 0}]]}
	return {
		'name': f'__test__ harness [{webhook_path}]',
		'nodes': nodes,
		'connections': connections,
		'settings': {},
	}


def run_subworkflow_case(client, loader, sub_workflow_id, harness_id, webhook_path, case):
	"""Apply the case's pins to the sub-workflow copy, trigger it via the harness, and assert
	on the target node's output — following into the linked child execution when the asserted
	node lives inside the sub-workflow rather than being the harness's own Execute Workflow node."""
	sub_definition = loader.build_subworkflow_definition(case.get('pins', {}), webhook_path)
	client.update_workflow(sub_workflow_id, sub_definition)
	baseline_id = client.get_latest_execution_id(harness_id)
	client.trigger_webhook(webhook_path, case['input'])
	harness_execution = client.wait_for_execution(harness_id, after_id=baseline_id)
	target_node = case['assert']['node']
	if target_node == 'Execute Workflow':
		node_output = client.get_node_output(harness_execution, 'Execute Workflow')
	else:
		child_execution_id = client.get_child_execution_id(harness_execution, 'Execute Workflow')
		if child_execution_id is None:
			return [f'harness never linked a child execution (status={harness_execution.get("status")})']
		child_execution = client.get_execution(child_execution_id)
		node_output = client.get_node_output(child_execution, target_node)
	if node_output is None:
		return [f'node "{target_node}" never ran']
	failures = []
	for field, expected in case['assert']['fields'].items():
		actual = get_field(node_output, field)
		if actual != expected:
			failures.append(f'{field}: expected {expected!r}, got {actual!r}')
	return failures


def run_subworkflow_suite(client, loader, suite_path):
	"""Create one disposable sub-workflow copy plus one harness pointing at it for the whole
	suite file, reused across its cases — mirrors run_suite's one-workflow-per-suite lifecycle,
	just with two n8n entities instead of one."""
	suite = json.loads(suite_path.read_text(encoding='utf-8'))
	webhook_path = f'test-{suite["path"]}-{uuid.uuid4().hex[:8]}'
	sub_definition = loader.build_subworkflow_definition({}, webhook_path)
	sub_workflow_id = client.create_workflow(sub_definition)['id']
	harness_id = None
	results = []
	try:
		# n8n refuses to activate a caller whose Execute Workflow node points at an inactive
		# workflow ("Cannot publish workflow: ... references workflow X which is not published") —
		# the sub-workflow copy must be activated before the harness that calls it.
		client.activate_workflow(sub_workflow_id)
		skip_unwrap = suite.get('target_workflow') == 'context-enrichment.json'
		harness_definition = build_harness_definition(webhook_path, sub_workflow_id, skip_unwrap=skip_unwrap)
		harness_id = client.create_workflow(harness_definition)['id']
		client.activate_workflow(harness_id)
		for case in suite['cases']:
			try:
				failures = run_subworkflow_case(client, loader, sub_workflow_id, harness_id, webhook_path, case)
			except Exception as exc:  # keep going so one broken case doesn't hide the rest
				failures = [f'error: {exc}']
			results.append((f'{suite["path"]}: {case["description"]}', failures))
			time.sleep(CASE_THROTTLE_SECONDS)
	finally:
		if harness_id is not None:
			client.cleanup_workflow(harness_id)
		client.cleanup_workflow(sub_workflow_id)
	return results


def main():
	if len(sys.argv) < 2:
		print('Usage: python runner.py <path-to-workflow.json>')
		sys.exit(1)
	target_name = Path(sys.argv[1]).name
	loader = WorkflowLoader(sys.argv[1])
	client = N8nClient()
	run, case_dir = (run_subworkflow_suite, SUBWORKFLOW_CASE_DIR) if loader.is_subworkflow else (run_suite, CASE_DIR)
	all_results = []
	for suite_path in sorted(case_dir.glob('*.json')):
		if loader.is_subworkflow:
			# Multiple sub-workflow files can each have their own suite in this same directory —
			# a suite only applies to the one sub-workflow it names, not to whichever was loaded.
			suite_target = json.loads(suite_path.read_text(encoding='utf-8')).get('target_workflow')
			if suite_target != target_name:
				continue
		all_results.extend(run(client, loader, suite_path))
	failed = 0
	for description, failures in all_results:
		if failures:
			failed += 1
			print(f'not ok - {description}')
			for failure in failures:
				print(f'    {failure}')
		else:
			print(f'ok - {description}')
	print(f'\n{len(all_results) - failed}/{len(all_results)} passing')
	sys.exit(1 if failed else 0)


if __name__ == '__main__':
	main()
