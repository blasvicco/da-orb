import vm from 'node:vm';
import { makeContext } from './n8n_context.js';

export class NodeRunner {
  constructor(loader) {
    this._loader = loader;
  }

  run(nodeName, inputJson, nodeResults = {}, inputItems = null) {
    const result = this.runAll(nodeName, inputJson, nodeResults, inputItems)[0] ?? null;
    return result === null ? null : JSON.parse(JSON.stringify(result));
  }

  // Returns every item the node's code returns, not just the first — needed for nodes that
  // legitimately fan one input item out into several (e.g. Split Files, one item per
  // bucket_file_id). run() above stays the single-item accessor every existing test case
  // already relies on; this is additive, not a behavior change to run().
  // inputItems (optional) seeds $input.all() with several items, for a node reading multiple
  // current-node input items (e.g. Merge File Extractions reading N per-file results).
  runAll(nodeName, inputJson, nodeResults = {}, inputItems = null) {
    const code = this._loader.getCode(nodeName);
    if (!code) throw new Error(`No code node named "${nodeName}" in workflow`);
    const sandbox = { ...makeContext(inputJson, nodeResults, inputItems), __out: undefined };
    vm.runInNewContext(`__out = (function(){ ${code} })();`, sandbox);
    // A node configured with mode: "runOnceForEachItem" returns a single { json } object per
    // call (n8n itself requires this shape — an array return fails its own result validation
    // in that mode), unlike the default "runOnceForAllItems" nodes elsewhere in this codebase,
    // which return an array. Normalize both to an array here rather than making every test
    // case aware of which mode its target node uses.
    const out = Array.isArray(sandbox.__out) ? sandbox.__out : [sandbox.__out];
    const items = (out ?? []).map((item) => item?.json ?? null);
    // vm.runInNewContext runs in a separate V8 realm, so object/array literals built inside
    // the node's code carry a different Object/Array prototype than this realm's — that makes
    // assert.strict.deepEqual report structurally-identical values as unequal. Round-tripping
    // through JSON also matches how n8n itself serializes item data between node executions.
    return JSON.parse(JSON.stringify(items));
  }
}
