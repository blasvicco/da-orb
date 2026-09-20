import { readFileSync } from 'node:fs';

export class WorkflowLoader {
  // jsonPaths may be a single path or an array — Phase 2 split the workflow across
  // multiple files (spine + sub-workflows), and a test case doesn't care which file its
  // target node currently lives in, only that it can be found somewhere. Node names are
  // assumed unique across all provided files (true today; each sub-workflow renamed/moved
  // nodes rather than duplicating a name).
  constructor(jsonPaths) {
    const paths = Array.isArray(jsonPaths) ? jsonPaths : [jsonPaths];
    this._raws = paths.map((p) => JSON.parse(readFileSync(p, 'utf8')));
    this._raw = this._raws[0];
    this._nodes = new Map();
    for (const raw of this._raws) {
      for (const node of raw.nodes) this._nodes.set(node.name, node);
    }
  }

  getCode(name) {
    return this._nodes.get(name)?.parameters?.jsCode ?? null;
  }

  getConnections() {
    // Connections aren't merged across files (Tier 1 only ever inspects a single node's
    // own code in isolation, never cross-file wiring) — callers needing connections stay
    // scoped to the first-provided workflow, same as before this multi-file change.
    return this._raw.connections;
  }

  getNode(name) {
    return this._nodes.get(name) ?? null;
  }

  getNodeId(name) {
    return this._nodes.get(name)?.id ?? null;
  }

  listCodeNodes() {
    return [...this._nodes.values()]
      .filter((node) => node.type === 'n8n-nodes-base.code')
      .map((node) => node.name);
  }

  listNodeNames() {
    return [...this._nodes.keys()];
  }
}
