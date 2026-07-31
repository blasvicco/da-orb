// Usage: node run.js "../Orbot v4.json"
import { WorkflowLoader } from './engine/workflow_loader.js';
import { NodeRunner } from './engine/node_runner.js';
import { test, describe } from 'node:test';
import { strict as assert } from 'node:assert';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const wfPath = process.argv[2];
if (!wfPath) {
  console.error('Usage: node run.js <path-to-workflow.json>');
  process.exit(1);
}

const loader = new WorkflowLoader(wfPath);
const runner = new NodeRunner(loader);

const caseDir = new URL('cases/unit/', import.meta.url);
const files = await readdir(caseDir);

for (const file of files.filter((f) => f.endsWith('.json'))) {
  const suite = JSON.parse(await readFile(join(caseDir.pathname, file), 'utf8'));
  describe(suite.node, () => {
    for (const tc of suite.cases) {
      test(tc.description, () => {
        const result = runner.run(suite.node, tc.input, tc.nodeResults ?? {});
        for (const [key, expected] of Object.entries(tc.expected)) {
          assert.deepEqual(result?.[key], expected, `field: ${key}`);
        }
      });
    }
  });
}
