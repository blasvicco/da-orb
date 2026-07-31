export function makeContext(inputJson, nodeResults = {}) {
  const wrap = (data) => ({ first: () => ({ json: data }), all: () => [{ json: data }] });
  return {
    $input: wrap(inputJson),
    $json: inputJson,
    $: (name) => {
      if (!(name in nodeResults)) throw new Error(`Node "${name}" not in test context`);
      return wrap(nodeResults[name]);
    },
    Buffer,
  };
}
