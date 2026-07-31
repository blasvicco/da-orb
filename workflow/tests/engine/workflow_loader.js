import { readFileSync } from 'node:fs';

export class WorkflowLoader {
  constructor(jsonPath) {
    const raw = JSON.parse(readFileSync(jsonPath, 'utf8'));
    this._raw = raw;
    this._nodes = new Map(raw.nodes.map((node) => [node.name, node]));
  }

  getCode(name) {
    return this._nodes.get(name)?.parameters?.jsCode ?? null;
  }

  getConnections() {
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
