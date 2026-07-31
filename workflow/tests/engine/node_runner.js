import vm from 'node:vm';
import { makeContext } from './n8n_context.js';

export class NodeRunner {
  constructor(loader) {
    this._loader = loader;
  }

  run(nodeName, inputJson, nodeResults = {}) {
    const code = this._loader.getCode(nodeName);
    if (!code) throw new Error(`No code node named "${nodeName}" in workflow`);
    const sandbox = { ...makeContext(inputJson, nodeResults), __out: undefined };
    vm.runInNewContext(`__out = (function(){ ${code} })();`, sandbox);
    const result = sandbox.__out?.[0]?.json ?? null;
    // vm.runInNewContext runs in a separate V8 realm, so object/array literals built inside
    // the node's code carry a different Object/Array prototype than this realm's — that makes
    // assert.strict.deepEqual report structurally-identical values as unequal. Round-tripping
    // through JSON also matches how n8n itself serializes item data between node executions.
    return result === null ? null : JSON.parse(JSON.stringify(result));
  }
}
