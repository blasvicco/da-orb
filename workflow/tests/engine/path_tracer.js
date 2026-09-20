export class PathTracer {
  constructor(loader) {
    this._loader = loader;
  }

  getOutputs(nodeName) {
    const connections = this._loader.getConnections()[nodeName];
    if (!connections?.main) return [];
    return connections.main.map((edges, outputIndex) => ({
      outputIndex,
      outputKey: this._outputKey(nodeName, outputIndex),
      targets: (edges ?? []).map((edge) => edge.node),
    }));
  }

  listBranchNodes() {
    return this._loader.listNodeNames().filter((name) => {
      const type = this._loader.getNode(name)?.type;
      return type === 'n8n-nodes-base.switch' || type === 'n8n-nodes-base.if';
    });
  }

  tracePath(startNode, endNode) {
    const queue = [[startNode]];
    const seen = new Set([startNode]);
    while (queue.length) {
      const path = queue.shift();
      const last = path[path.length - 1];
      if (last === endNode) return path;
      for (const { targets } of this.getOutputs(last)) {
        for (const target of targets) {
          if (seen.has(target)) continue;
          seen.add(target);
          queue.push([...path, target]);
        }
      }
    }
    return null;
  }

  _outputKey(nodeName, outputIndex) {
    const rules = this._loader.getNode(nodeName)?.parameters?.rules?.values;
    return rules?.[outputIndex]?.outputKey ?? String(outputIndex);
  }
}
