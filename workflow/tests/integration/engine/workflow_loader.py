"""Builds an isolated, disposable copy of a workflow definition for the n8n REST API."""
import copy
import json

# additionalProperties is false on n8n's workflowSettings schema, so only forward fields it
# actually recognizes — the source file also carries editor-only fields (e.g. binaryMode) that
# the public API rejects outright.
SETTINGS_ALLOWLIST = {
	'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
	'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone',
	'executionOrder', 'callerPolicy', 'callerIds', 'timeSavedPerExecution', 'availableInMCP',
}


class WorkflowLoader:
	def __init__(self, json_path):
		"""Load the workflow JSON once; every test definition is built from this snapshot."""
		with open(json_path, encoding='utf-8') as source_file:
			self._workflow = json.load(source_file)
		self._webhook_path = self._find_webhook_path()

	def build_test_definition(self, webhook_path, pins):
		"""Return a create/update-ready body with an isolated webhook path and pinned nodes swapped for deterministic stand-ins."""
		# n8n silently ignores pinData on active/webhook-triggered executions (verified against
		# a live instance) — pinning only applies to manual editor runs. Node substitution is the
		# only way to get deterministic output from a real webhook-triggered execution.
		nodes = copy.deepcopy(self._workflow['nodes'])
		connections = copy.deepcopy(self._workflow['connections'])
		self._rewrite_webhook_path(nodes, webhook_path)
		self._apply_pins(nodes, connections, pins)
		settings = {key: value for key, value in (self._workflow.get('settings') or {}).items() if key in SETTINGS_ALLOWLIST}
		return {
			'name': f'__test__ {self._workflow["name"]} [{webhook_path}]',
			'nodes': nodes,
			'connections': connections,
			'settings': settings,
		}

	def _apply_pins(self, nodes, connections, pins):
		# Two pin styles: a plain dict becomes the pinned node's literal success output; a dict
		# with a top-level "__error__" key instead simulates that node's native error output —
		# needed because a Code node has only one main output, so it can't reach whatever a real
		# node's dedicated error-output branch targets unless we redirect its connections there.
		for node in nodes:
			if node['name'] not in pins:
				continue
			spec = pins[node['name']]
			error_payload = spec.get('__error__') if isinstance(spec, dict) else None
			node['type'] = 'n8n-nodes-base.code'
			node['typeVersion'] = 2
			node.pop('credentials', None)
			node.pop('webhookId', None)
			output = json.dumps(error_payload if error_payload is not None else spec)
			node['parameters'] = {'jsCode': f'return [{{ json: {output} }}];'}
			if error_payload is not None:
				connections[node['name']] = {'main': [self._original_error_targets(node['name'])]}
		self._strip_stale_side_connections(connections, set(pins))

	def _find_webhook_path(self):
		for node in self._workflow['nodes']:
			if node['type'] == 'n8n-nodes-base.webhook':
				return node['parameters']['path']
		raise ValueError('No webhook node found in workflow')

	def _original_error_targets(self, node_name):
		main_outputs = self._workflow['connections'].get(node_name, {}).get('main', [])
		return copy.deepcopy(main_outputs[1]) if len(main_outputs) > 1 else []

	def _rewrite_webhook_path(self, nodes, webhook_path):
		original = f'/webhook/{self._webhook_path}'
		replacement = f'/webhook/{webhook_path}'
		for node in nodes:
			if node['type'] == 'n8n-nodes-base.webhook':
				node['parameters']['path'] = webhook_path
			url = node.get('parameters', {}).get('url')
			if isinstance(url, str) and original in url:
				node['parameters']['url'] = url.replace(original, replacement)

	@staticmethod
	def _strip_stale_side_connections(connections, pinned_names):
		# Pinned Agent nodes lose their ai_languageModel/ai_tool sub-node inputs — a Code node
		# doesn't declare those input types, so leaving the edges in place would fail validation.
		for outputs_by_type in connections.values():
			for conn_type, outputs in list(outputs_by_type.items()):
				if conn_type == 'main':
					continue
				outputs_by_type[conn_type] = [
					[edge for edge in output if edge['node'] not in pinned_names]
					for output in outputs
				]
