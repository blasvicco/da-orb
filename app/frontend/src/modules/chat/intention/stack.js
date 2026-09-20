// intention_nodes entries carry no display label — fall back to the process
// definition's name, then the raw process_id slug.
const labelFor = (processId, processDefinition) => processDefinition?.name || processId || '';

// The most recent message that carries a `state` snapshot is the only source of
// truth for the intention graph — earlier messages go stale once a turn completes.
const latestState = (messages) => {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    if (messages[idx]?.state) return messages[idx].state;
  }
  return null;
};

// fallbackState covers the reloaded-session case: history loaded via the REST API
// carries no per-message `state` (only live websocket messages do), so the caller
// passes the session's own persisted n8n_state to use once no message has one.
export const deriveIntentionNodes = (messages, fallbackState) => {
  const state = latestState(messages || []) || fallbackState || null;
  if (!state) return [];
  // intention_nodes is keyed by each node's own id (Record<id, Node>) -- the single
  // source of truth for a node's process_id/process_definition/form_state, no separate
  // root-level copy anymore.
  const nodes = Object.values(state.intention_nodes || {});

  return nodes.map((node) => ({
    id: node.id,
    label: labelFor(node.process_id, node.process_definition),
    parentId: node.parent_id,
    status: node.status,
    errorDetail: node.error_detail ?? null,
  }));
};

// Nests the flat, parent_id-linked intention list into the {key, title, children}
// shape a-tree expects — a node whose parent isn't (or is no longer) in the list
// becomes a root, so the tree always renders even with a partial/stale chain.
export const buildIntentionTree = (nodes) => {
  const wrapped = new Map(nodes.map((node) => [node.id, { ...node, children: [], key: node.id, title: node.label }]));
  const roots = [];
  nodes.forEach((node) => {
    const entry = wrapped.get(node.id);
    const parent = node.parentId != null ? wrapped.get(node.parentId) : null;
    if (parent) {
      parent.children.push(entry);
    } else {
      roots.push(entry);
    }
  });
  return roots;
};
