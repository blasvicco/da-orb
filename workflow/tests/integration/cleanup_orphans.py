"""Usage: python cleanup_orphans.py

Sweeps and removes any leftover __test__ workflows (runner.py's naming convention for its own
disposable test copies, see build_test_definition/build_subworkflow_definition/
build_harness_definition) that a prior interrupted or failed run left behind -- deactivated if
still active, then deleted. A safety net for cases runner.py's own retry-hardened cleanup still
can't reach (e.g. n8n was fully down at the moment cleanup ran). Confirmed live: a period of n8n
instability during a long testing session left 7 such orphans behind, 5 of them still active
(webhook registered, consuming resources) -- worth running this after any interrupted Tier 2 run.
"""
from engine.n8n_client import N8nClient


def main():
	client = N8nClient()
	orphans = [w for w in client.list_workflows() if w['name'].startswith('__test__')]
	if not orphans:
		print('no leftover __test__ workflows found')
		return

	print(f'found {len(orphans)} leftover __test__ workflow(s):')
	for workflow in orphans:
		print(f"  - {workflow['id']} {workflow['name']} (active={workflow.get('active')})")
		client.cleanup_workflow(workflow['id'])
	print(f'cleaned up {len(orphans)} orphan(s)')


if __name__ == '__main__':
	main()
