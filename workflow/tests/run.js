// Usage: node run.js "../Orbot v4.json" [additional-workflow.json ...]
// Multiple paths let a test suite span a spine + its sub-workflow files (Phase 2) — a
// test case just names its target node, not which file it currently lives in.
import { WorkflowLoader } from './engine/workflow_loader.js';
import { NodeRunner } from './engine/node_runner.js';
import { test, describe } from 'node:test';
import { strict as assert } from 'node:assert';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const wfPaths = process.argv.slice(2);
if (!wfPaths.length) {
  console.error('Usage: node run.js <path-to-workflow.json> [additional-workflow.json ...]');
  process.exit(1);
}

const loader = new WorkflowLoader(wfPaths);
const runner = new NodeRunner(loader);

const caseDir = new URL('cases/unit/', import.meta.url);
const files = await readdir(caseDir);

for (const file of files.filter((f) => f.endsWith('.json'))) {
  const suite = JSON.parse(await readFile(join(caseDir.pathname, file), 'utf8'));
  describe(suite.node, () => {
    for (const tc of suite.cases) {
      test(tc.description, () => {
        if (tc.expectedItems) {
          // Node fans one input item out into several (e.g. Split Files) — check each
          // returned item's listed fields against its corresponding entry, in order.
          const items = runner.runAll(suite.node, tc.input, tc.nodeResults ?? {}, tc.inputItems ?? null);
          assert.equal(items.length, tc.expectedItems.length, 'item count');
          tc.expectedItems.forEach((expectedItem, i) => {
            for (const [key, expected] of Object.entries(expectedItem)) {
              assert.deepEqual(items[i]?.[key], expected, `item ${i} field: ${key}`);
            }
          });
          return;
        }
        const result = runner.run(suite.node, tc.input, tc.nodeResults ?? {}, tc.inputItems ?? null);
        for (const [key, expected] of Object.entries(tc.expected)) {
          assert.deepEqual(result?.[key], expected, `field: ${key}`);
        }
      });
    }
  });
}
