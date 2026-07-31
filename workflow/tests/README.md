# Workflow Test Framework

Tests an Orbot workflow JSON file directly — no live webhook, no real LLM/SAP calls required
for Tier 1, and no changes to your live n8n workflow for Tier 2. See
[`docs/plans/workflow_test_framework.md`](../../docs/plans/workflow_test_framework.md) for the
original design. This file documents how to actually run it.

All commands below run through SSH per this repo's `CLAUDE.md` — nothing here runs locally.

## One-time setup

Tier 2 needs the `workflow` directory mounted into the `backend` container. This is already
in `docker-compose.yml`:

```yaml
backend:
  volumes:
    - ./app/backend:/home/app
    - ./workflow:/home/workflow
```

If that mount isn't live yet, restart the service (ask before doing this in a shared/running
environment):

```bash
ssh -p 8532 blas@blas.local "cd /Volumes/Data/Users/blas/Workspace/da-orb && docker compose up -d backend"
```

Tier 2 also needs `N8N_API_KEY` available inside the `backend` container — it already is, via
`app/.env.common.dev`.

## Running everything

```bash
./workflow/tests/run.sh "workflow/Orbot v4.json"
```

Runs Tier 1 then Tier 2 against the given workflow file and prints both results. Swap in
`"workflow/Orbot v3.json"` (or any other version) to test that file instead — nothing about the
framework itself needs to change.

## Running Tier 1 (unit tests) only

```bash
ssh -p 8532 blas@blas.local \
  "docker run --rm -v '/Volumes/Data/Users/blas/Workspace/da-orb/workflow:/workflow' node:20-alpine \
   node /workflow/tests/run.js '/workflow/Orbot v4.json'"
```

Extracts each `n8n-nodes-base.code` node's JS from the workflow JSON and runs it directly in a
`vm` sandbox against the cases in `cases/unit/*.json`. No network calls, no n8n instance
required — this is why it also runs in a bare `node:20-alpine` container. Prints TAP output;
exits non-zero if any case fails.

## Running Tier 2 (integration tests) only

```bash
ssh -p 8532 blas@blas.local \
  "docker exec da-sapot-backend python3 /home/workflow/tests/integration/runner.py '/home/workflow/Orbot v4.json'"
```

For each file in `cases/integration/*.json`, creates a **disposable, isolated copy** of the
workflow in n8n (own webhook path, own workflow ID), activates it, runs each case's `input`
through its live webhook, polls `/api/v1/executions` for the result, asserts on the target
node's output, then deactivates and deletes the copy. Your actual "Orbot v3" workflow already
running in n8n is never read from or written to.

Nodes named in a case's `pins` are swapped for a deterministic Code-node stand-in that just
returns the given JSON — this is *not* n8n's `pinData` field, because n8n silently ignores
`pinData` on webhook-triggered (as opposed to manual/editor) executions, so it wouldn't do
anything useful here. See `engine/workflow_loader.py`'s `_apply_pins` for exactly how this
works, including the `__error__` pin variant used to simulate a node's native error-output path
(e.g. an Agent node failing) rather than its normal success output.

Requires `N8N_API_KEY` in the `backend` container's environment and network access to
`da-sapot-n8n-main` — both already true in this repo's `docker-compose.yml`.

## Writing new test cases

No code changes needed — every case is a plain JSON file.

### Tier 1 — `cases/unit/<node_name>.json`

```json
{
  "node": "Parse & Enrich",
  "cases": [
    {
      "description": "defaults language to es when session.language missing",
      "input": { "body": { "message": "hola", "session": {} } },
      "nodeResults": {},
      "expected": { "language": "es", "expertise_level": 2 }
    }
  ]
}
```

- `node` — exact node name as it appears in the workflow JSON.
- `input` — becomes `$input`/`$json` inside the node's code.
- `nodeResults` — optional; supplies whatever `$('Other Node')` calls the code makes. Omitting
  a referenced node name makes `$()` throw for it, same as when that node genuinely didn't run
  in the real workflow (many handler nodes rely on this via `try { $('X')... } catch {}`
  fallback chains).
- `expected` — top-level fields to check with `assert.deepEqual` against the node's returned
  json. Nested objects/arrays work fine; there's no support for asserting a field is *absent*
  (`undefined` isn't JSON-representable), so design cases around fields that have a concrete
  value either way.

### Tier 2 — `cases/integration/path_<name>.json`

```json
{
  "path": "find",
  "cases": [
    {
      "description": "Agent: Find returns a match -> Handler: Match loads the standard_path",
      "input": { "message": "quiero hacer una solicitud de compra", "session": { "language": "es" } },
      "pins": {
        "Agent: Find": { "output": "{\"status\":\"match\",\"path\":\"purchase/purch_request/purch_request.json\"}" }
      },
      "assert": { "node": "Handler: Match", "fields": { "standard_path": "purchase/purch_request/purch_request.json" } }
    }
  ]
}
```

- `path` — groups cases in one file into a single disposable workflow, reused across them
  (cheaper than one workflow per case).
- `input` — the raw JSON POSTed to the workflow's webhook (arrives as `body` inside the
  workflow, matching what `Parse & Enrich` reads).
- `pins` — node name → literal output. A plain object becomes that node's success output
  (e.g. `{"output": "..."}"` for an Agent node, `{"statusCode": 200, "body": {...}}` for an
  HTTP Request node). `{"__error__": {...}}` instead routes through that node's real
  error-output connections with the given payload.
- `assert.fields` — dotted paths are supported (`"state.process_id"`) for reaching into nested
  objects on the asserted node's output.

**Watch out for `Parse & Enrich`'s `SWITCH_PATTERN`** when writing `input.message` for a case
with an active `process_id`: words like "cancelar", "salir", "switch", or "instead" flip
`switch_intent` to `true` in the code itself, before any pinned agent even runs — this bit one
of the existing `path_fill_form.json` cases during development (see the node's code for the
full keyword list).

**Cascades**: triggering a case doesn't stop execution at your asserted node — the whole
workflow runs to completion (Tier 2 waits on the execution's terminal status, not on any single
node). If the branch under test can loop back into `Classify Intent` and reach another Agent
node downstream (e.g. a matched process falling through to `fill_form`), pin that node too with
a neutral stub, or the cascade will make a real OpenAI/SAP call.

## Troubleshooting

- **Tier 2 case fails with `node "X" never ran`**: either the workflow didn't take the branch
  you expected (check `input` against the relevant `Classify Intent` / `Switch: Route by
  Status` condition), or — if cases in the same suite file are failing intermittently — the
  execution-polling logic in `N8nClient.wait_for_execution` picked up a stale execution; it
  already guards against this via `after_id`, but if you see it again check that `run_case`
  is still capturing `get_latest_execution_id` *before* calling `trigger_webhook`.
- **`delete_workflow` briefly 500s**: expected for a suite (like `path_queue.json`) whose last
  case triggers a chain of recursive self-calls — `delete_workflow` already retries a few times
  with a short backoff for this.
- **A Tier 2 run leaves an orphaned `__test__ ...` workflow in n8n**: this shouldn't happen
  (cleanup runs in a `finally` block), but if a run was killed mid-flight, list and remove it:
  `GET/DELETE /api/v1/workflows` on `da-sapot-n8n-main`, filtering by name prefix `__test__`.

## Verifying the framework itself still detects regressions

Not part of normal test runs, but worth knowing: make a scratch copy of the workflow JSON with
a deliberate one-line break in a node covered by a unit test case (e.g. flip a default value
`Parse & Enrich` returns), point Tier 1 at the scratch copy, and confirm the relevant case fails
with a clear expected/actual diff. Don't edit the checked-in workflow JSON files for this —
copy them out first.
