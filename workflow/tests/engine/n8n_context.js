export function makeContext(inputJson, nodeResults = {}, inputItems = null) {
  // A referenced node's result can be a single object (the common case: that node ran once,
  // .first()/.item/.itemMatching(0) all resolve to it) or an array (that node emitted several
  // items — needed to test code using $('NodeName').itemMatching(i) to recover per-item
  // lineage across a fan-out, e.g. Normalize Extraction Result tracing rows back to which of
  // several trigger items produced them).
  const wrap = (data) => {
    const nodeItems = Array.isArray(data) ? data : [data];
    return {
      first: () => ({ json: nodeItems[0] }),
      all: () => nodeItems.map((json) => ({ json })),
      item: { json: nodeItems[0] },
      itemMatching: (i) => ({ json: nodeItems[i] }),
    };
  };
  // inputItems lets a test seed $input.all() with several items (e.g. Merge File
  // Extractions reading N per-file results) — defaulting to [inputJson] keeps every
  // existing single-item test's $json/$input.first()/$input.all() behavior unchanged.
  const items = inputItems ?? [inputJson];
  return {
    $input: { first: () => ({ json: items[0] }), all: () => items.map((json) => ({ json })) },
    $json: items[0],
    $: (name) => {
      if (!(name in nodeResults)) throw new Error(`Node "${name}" not in test context`);
      return wrap(nodeResults[name]);
    },
    $execution: { id: 'test-execution-id' },
    Buffer,
  };
}
