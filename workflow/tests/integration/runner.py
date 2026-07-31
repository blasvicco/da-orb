"""Entry point: python runner.py <workflow.json>

Runs each cases/integration/*.json suite against a disposable copy of the target workflow
created (and torn down) in n8n for that suite alone — the live workflow already deployed in
n8n is never touched. See engine/workflow_loader.py for why pinning works by node
substitution rather than n8n's pinData (which is ignored on webhook-triggered executions).
"""
import json
import sys
import uuid
from pathlib import Path

from engine.n8n_client import N8nClient
from engine.workflow_loader import WorkflowLoader

CASE_DIR = Path(__file__).parent.parent / 'cases' / 'integration'


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
	finally:
		client.deactivate_workflow(workflow_id)
		client.delete_workflow(workflow_id)
	return results


def main():
	if len(sys.argv) < 2:
		print('Usage: python runner.py <path-to-workflow.json>')
		sys.exit(1)
	loader = WorkflowLoader(sys.argv[1])
	client = N8nClient()
	all_results = []
	for suite_path in sorted(CASE_DIR.glob('*.json')):
		all_results.extend(run_suite(client, loader, suite_path))
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
