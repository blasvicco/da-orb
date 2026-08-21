# Intention Graph — Use Case Catalog

Status: **verified against live code.** Every claim in this folder was traced directly from the current `workflow/Orbot v14/*.json` files, the Django backend (`app/backend/`), and the Vue frontend (`app/frontend/src/`) — not from design docs or memory. Where a design doc under `docs/plans/` describes something different (e.g. `batch_multi_process_support.md` describes a two-pass classify-then-extract batch design against an earlier workflow version), that doc is **superseded** by what's actually implemented in v14; this folder documents the real, current behavior.

Purpose: give every supported user-facing flow a precise, node-level trace — which workflow files and nodes activate, in what order, and how values mutate at each step — so each one can be turned into a spec test (Tier 1 unit case, Tier 2 integration path, or a live E2E script under `workflow/tests/integration/`) with minimal extra investigation.

## How to read a use-case doc

Each doc follows the same shape:

1. **Scenario** — the user-facing story, in plain example-message form.
2. **Preconditions** — what state (if any) must already exist before the scenario's first turn.
3. **Turn-by-turn trace** — for each user message, the ordered list of workflow files + nodes that run, with the key value mutations at each hop (input → output, field by field, for the fields that matter to that use case).
4. **Final state** — what `intention_nodes`/`active_node_id`/delivered-message-type look like once the scenario completes.
5. **Spec test outline** — a structured skeleton (not full code) showing how to pin/assert this scenario using the existing test harness conventions (see below), plus a pointer to the closest existing test file to model it on.

## Architecture overview

### The spine (every turn, always, in this order)

Every chat message enters through one workflow, `spine.json` (n8n workflow id `gl7Ax8b77WhVUTmw`, webhook path `/webhook/chat`). Its nodes run in a fixed sequence regardless of what the message says:

```
Webhook
  -> Capture Root Execution        (stamps _root_execution_id, used later for token-usage accounting)
  -> Context Enrichment            (oZZLcG0NvmTtMiis) -- normalizes the raw body, drops dead fields, runs file extraction
  -> Agent: Intent Finder          (FBxYP5ltZeEseUuc) -- classifies the message, computes route_key
  -> Intent Manager                (ytOCDPmatCa5qaxb) -- parks the currently-active node if a new/different intent is starting
  -> Context Update                (iD1HEeXReW1SXsI4) -- resolves process schema(s) from GitHub, creates a new intention_nodes entry if needed
  -> Router                        (switch on route_key)
       -> General Inquiry              (zjREXKZ0zunTw3I9)   route_key === 'general_inquiry'
       -> SAP: Process Form Filling    (iUUtXFfbvCxYPZVU)   route_key === 'sap_form_filling'
       -> SAP: Inquiry Execution       (1yNcmr17XAakSJo0)   route_key === 'sap_inquiry_execution' -- DEAD BRANCH, see note below
       -> Batch Processing             (M2ZeV5WXqSY2rXeX)   route_key === 'batch_processing'
       -> SAP: Discovery               (bDMyP4ISLUjViWpG)   route_key === 'sap_discovery' -- see UC-13
       -> Unmatched Route (debug)      fallback, route_key matched nothing above
```

**Dead branch, worth knowing about:** the Router's `sap_inquiry_execution` output is wired to a real node (`SAP: Inquiry Execution`), but `Agent: Find`'s own code comment states it "*deliberately never produces 'sap_inquiry_execution'*" — nothing in the live system ever sets `route_key` to that value. The only place this route fires is a pinned Tier 2 test (`workflow/tests/cases/integration/path_backbone.json`). In real traffic, SAP execution always happens as an **internal** call from inside `sap-process-form-filling.json` (see UC-1), never via this top-level Router branch.

### `route_key` — the only five live values

Computed once, by `agent-intent-finder.json`'s `Compute Route Key` node, right after `Agent: Find` classifies the message:

| `route_key` | When | Set by |
|---|---|---|
| `general_inquiry` | `Agent: Find` status = `general_inquiry` | not a SAP action, not a reply to a pending question |
| `sap_form_filling` | `pending_reply`, or `new_intent` + `new_intent_status: "match"` | continuing an open form, or starting exactly one new process |
| `batch_processing` | `new_intent` + `new_intent_status: "batch"` | 2+ distinct process instances requested in one message (same process type repeated, or different process types mixed) |
| `sap_discovery` | `new_intent` + `new_intent_status: "discover"` | a legitimate SAP lookup question that no cataloged process (alone or combined) can answer — see UC-13 |
| *(null, error path)* | `new_intent_status: "no_match"` / `"error"`, or unparseable | routed to the shared Error Parser instead of the Router |

### The error gate (`error-parser.json`)

Every flow above hits the same recurring shape after an LLM agent call, and again after computing that turn's outcome: check whether something went wrong; if so, classify it into a stable code + localized message and stop; if not, parse the agent's raw JSON `output` and keep going. This shared shape lives in one sub-workflow, `error-parser.json`:

```
error-parser.json:  Trigger -> Has Error? (Boolean($json.error))
                       true:  Classify & Store Error -> Clear Route Key -> return
                       false: Extract JSON (parses $json.output into _parsed) -> return
```

Every caller invokes this **directly**, twice per turn:

- **Right after its own agent node** (`Agent: Find`, `Agent: Form`, `Agent: Execute`, `Agent: Context & Conversation`) — both of the agent's outputs (success and `continueErrorOutput`) wire straight into the call. An Agent node's own output replaces the item's json entirely, so the pre-agent context is restored via a small `Set` node, `Merge Context: X`, immediately before the call — not a bespoke Code node. The caller then checks `Boolean($json.error)` itself (`Was Handled? (Agent)`) to decide whether to skip straight to its own delivery step or continue with `_parsed`.
- **Right after its own outcome-computing node** (`Compute Route Key` / `Compute Execution Outcome` / `Compute Form Outcome`, or `context-update.json`'s schema-resolution outcome) — no context-merge needed here, since that node already carries full context forward. Some callers need their own `Was Handled? (Outcome)` IF afterward; `sap-inquiry-execution.json` doesn't, since both outcomes at that point already converge on the same next node (`Suppress Delivery?`).

`error-parser.json` never calls `Execute Workflow: Response` itself — delivery stays an explicit, caller-controlled step (`sap-inquiry-execution.json`'s `suppress_delivery` gate has to sit between classification and delivery on *both* outcomes, which a gate nested inside the shared workflow couldn't know about). See UC-1/UC-8/UC-10/UC-11 for this mechanism traced through real scenarios.

### State shape (Redis, `N8nSessionState`, `app/backend/web_socket/helpers/n8n/state.py`)

```json
{
  "active_node_id": "1#0",
  "intention_nodes": {
    "1#0": {
      "id": "1#0",
      "parent_id": null,
      "process_id": 1,
      "process_definition": { "...": "the full fetched process JSON, see Schema Resolution below" },
      "form_state": { "...": "whatever fields have been collected so far" },
      "status": "active"
    }
  },
  "last_bot_message": "..."
}
```

- `intention_nodes` is an **object keyed by each node's own id** (`Record<id, Node>`), not an array. Node ids are minted as `` `${processId}#${count}` `` — the *only* place this happens is the shared `register-intention-node.json` sub-workflow (`Register Node`), called both by `context-update.json`'s single-match path (`Prepare Node Registration` → `Execute Workflow: Register Intention Node`) and by `batch-processing.json`'s own final registration pass (see below) — not duplicated in either caller.
- `status` is one of `active` / `paused` / `completed` / `abandoned` / `failed`. `abandoned` is set by `sap-process-form-filling.json`'s `Compute Form Outcome` when the user cancels a form mid-fill, and treated as terminal (same as `completed`) by the auto-resume walk below — nothing ever auto-sets `failed` on the live graph (only batch's own throwaway synthetic nodes use it, see UC-2).
- This is the **entire** persisted state. There is no root-level `process_id`/`form_state`/`process_definition` mirror, no `paused_node_ids` array, no `process_queue`, no `last_error`/`last_batch_result`/round-tripped `intents`. Every consumer reads a node's own data via `intention_nodes[active_node_id]`.
- **Batch items get their own real `intention_nodes` entries, one per actual record/query, not one per intent.** `batch-processing.json` defers all registration to a single pass after every record's own outcome is known (`Check Registration Needed`, which fans out directly into per-registration items → `Has Registrations?` → one `Execute Workflow: Register Intention Node` call → `Resolve Final State`, which auto-resumes `active_node_id` to whatever the batch turn interrupted (`new_process_parent_id`), if it's still open — see UC-2/UC-4), never per-record — each record only ever records *what happened* (`_record_result`/`_pending_registration`), since neither `splitInBatches` nor a branch-then-reconverge topology of genuinely independent sources reliably threads/combines data across parallel graph paths (see UC-2's architecture note) and per-record registration would silently collide node ids. See UC-2 for the full mechanism and why per-record (not per-intent) granularity matters for recovery.

### The wire payload (what the frontend/Django actually sends to n8n)

`N8nClient.fire()` (`app/backend/web_socket/helpers/n8n/client.py`) POSTs to `/webhook/chat`:

```json
{
  "active_node_id": "...",
  "bucket_file_ids": [1, 2],
  "expertise_level": 2,
  "group_name": "chat_<org>_<user>_<chat_key>",
  "intention_nodes": { "...": "current Redis state" },
  "message": "the user's text",
  "organization": { "...": "safe_to_dict()" },
  "session": { "...": "resolved per auth driver" },
  "session_id": 123,
  "last_bot_message": "... (only when set)"
}
```

There is **no** `active_node_override` field — clicking a graph node is resolved directly in Django (UC-6), n8n never sees it. There is **no** `process_queue` field either — multi-instance requests are handled as a batch (UC-5), not a queue.

### The callback (what n8n sends back to Django)

Every flow ends by calling `response.json`'s `Build Callback Payload`, which POSTs to Django's `n8n_callback` endpoint:

```json
{
  "group_name": "...", "session_id": 123,
  "text": "the reply text",
  "type": "agent | alert",
  "root_execution_id": "... (for token-usage accounting)",
  "state": { "last_bot_message": "...", "intention_nodes": {"...": "..."}, "active_node_id": "..." },
  "processes": null
}
```

Django's `_resolve_and_persist_state` (`app/backend/drf_api/resources/chat/main.py`) merges only `active_node_id` / `intention_nodes` / `last_bot_message` from `state` into Redis — nothing else in that object round-trips to a later turn.

### Workflow file glossary

| File | Role |
|---|---|
| `spine.json` | entry point, routing |
| `context-enrichment.json` | normalizes the raw webhook body; triggers file extraction |
| `file-extraction-core.json` / `file-extraction-item.json` / `file-content-extractor.json` | turns `bucket_file_ids` into `extracted_files` (see UC-3, UC-12) |
| `agent-intent-finder.json` | classifies the message (`Agent: Find`), computes `route_key`; also runs `Agent: Intention Focus` for mid-conversation disambiguation |
| `intent-manager.json` | parks the active node before a new/different intent starts |
| `context-update.json` | resolves process schema(s) via `schema-resolution.json`; registers a new `intention_nodes` entry for a single match via `register-intention-node.json`; for a batch turn, also runs `Agent: Extract Batch Records` per process (one-shot record/filter extraction) |
| `schema-resolution.json` | fetches a process definition from GitHub (3-tier: DB override → org override → standard), plus its companion schema file |
| `register-intention-node.json` | shared node-minting step (`Register Node`) — the only place `intention_nodes` ids get minted; called by both `context-update.json` (single match) and `batch-processing.json` (one call per turn, registering every record/query from the whole batch at once) |
| `general-inquiry.json` | answers side questions using current state as context |
| `sap-process-form-filling.json` | the conversational form-fill loop (`Agent: Form`); calls SAP execution internally once confirmed. `Agent: Form` also has an optional `send_status` tool (`Orb MCP` node → `backendmcp.blas.local:3002/mcp`, from the sibling `da-orb-mcp` repo) it may call mid-turn to push free-form progress text via the same `n8n_callback` `type: "status"` channel — supplementary to, not a replacement for, the deterministic `Status: Collecting`/`Status: Submitting` pings every SAP-calling flow already fires |
| `sap-inquiry-execution.json` | actually calls SAP (`Agent: Execute` + SAP MCP tool) — GET_SINGLE / GET_QUERY / POST_CREATE |
| `batch-processing.json` | thin loop only, no agent of any kind: flattens every already-extracted record into one list, calls `sap-inquiry-execution.json` once per record via `mode: "each"` and `suppress_delivery` (GET or CREATE alike — it never branches on process type) — composes one summary, then registers a real `intention_nodes` entry per record/query from the whole turn via `register-intention-node.json` |
| `error-parser.json` | shared classify-or-extract gate used by every flow above — see "The error gate" below |
| `response.json` | shared terminal delivery step — the only place that calls Django's callback |

### Existing test harness (what "spec test" means in this repo)

- **Tier 1** (`workflow/tests/run.js`, sandboxed `vm`): pure unit tests for individual code nodes. Cases live in `workflow/tests/cases/unit/*.json`, one file per node, each with an `input`/`nodeResults`/`expected` triple. Run via `docker run --rm -v <repo>/workflow:/workflow node:20-alpine node /workflow/tests/run.js <every Orbot v14 *.json file>` (needs the full file set for cross-file node lookups). **Strict equality** — an absent key must be omitted from `expected`, not asserted as `null`.
- **Tier 2** (`workflow/tests/integration/runner.py`): live E2E via disposable workflow copies, one JSON file per source workflow under `workflow/tests/cases/integration/subworkflows/*.json`. Each case pins specific nodes' outputs (`"pins": {"NodeName": {...}}`) so an LLM call inside that sub-workflow doesn't need to actually run, and asserts fields on one target node's real output (`"assert": {"node": "...", "fields": {...}}`). **Loose equality** (Python `None`), so an absent field CAN be asserted as `null`.
- **Live E2E scripts** (`workflow/tests/integration/*_test.py`): standalone Python scripts that hit the real `/webhook/chat` webhook and poll Django's real REST API for delivery — no pins, real OpenAI calls, real state in Redis. Reserve these for the scenarios that are either (a) impossible to pin realistically (multi-turn conversational classification) or (b) explicitly need to prove a live regression guard. Model new ones on `workflow/tests/integration/phase4a_intention_nodes_object_shape_test.py` or `active_node_switch_django_direct_test.py`.

## Use case index

| # | Use case | Doc |
|---|---|---|
| 1 | Single new process request (baseline) | [01_single_new_process_request.md](01_single_new_process_request.md) |
| 2 | Multiple distinct intents in one message | [02_multiple_intents_one_message.md](02_multiple_intents_one_message.md) |
| 3 | File upload → batch creation from file content | [03_file_upload_batch_creation.md](03_file_upload_batch_creation.md) |
| 4 | Interrupt an active process with a new one (park/resume) | [04_interrupt_and_resume.md](04_interrupt_and_resume.md) |
| 5 | Multiple instances of the *same* process in one message | [05_multi_instance_same_process.md](05_multi_instance_same_process.md) |
| 6 | Click a node in the Intention Graph sidebar to resume it | [06_click_to_resume_intention_graph.md](06_click_to_resume_intention_graph.md) |
| 7 | Load a previous chat session | [07_load_previous_session.md](07_load_previous_session.md) |
| 8 | General inquiry / context question mid-flow | [08_general_inquiry_context_question.md](08_general_inquiry_context_question.md) |
| 9 | Search/query (GET) process, e.g. "list vendors" | [09_search_query_process.md](09_search_query_process.md) |
| 10 | Ambiguous request needing clarification | [10_ambiguous_request_clarification.md](10_ambiguous_request_clarification.md) |
| 11 | Error handling (SAP rejection + retry, hard agent failure, auth error) | [11_error_handling.md](11_error_handling.md) |
| 12 | Attach a file as context for a question (not for record creation) | [12_file_as_context_for_question.md](12_file_as_context_for_question.md) |
| 13 | Cross-entity discovery (no cataloged process fits) | [13_cross_entity_discovery.md](13_cross_entity_discovery.md) |

## Known gaps / discrepancies surfaced while researching this catalog

Not bugs to fix here — flagged so a spec test doesn't accidentally "prove" behavior that's actually just an untested edge:

- **File download has no error handling.** `file-extraction-item.json`'s "Download File" node has no `neverError`/`continueOnFail` set — a failed or expired presigned URL throws and fails that file's extraction sub-execution, rather than degrading into an `error` field on `extracted_files` the way every other failure mode in that pipeline does.
- **Batch: two very different failure behaviors.** A schema-resolution failure for one intent (e.g. process not found) is tolerated — that intent is skipped, the loop continues, and it's reported in the final summary. A live agent/tool failure during execution (e.g. an LLM rate limit) aborts the **entire** batch immediately, abandoning any not-yet-processed intents. A GET-type intent's own graceful `SAP_ERROR` (bad filter, no permission) falls into the first category, same tolerance a failed create already gets — only a genuine agent/tool crash inside `sap-inquiry-execution.json` (classified to anything other than `SAP_ERROR`) triggers the second. See UC-2/UC-5's error-path notes.
- **No caching in Schema Resolution.** Every process reference re-fetches from GitHub (2–4 API calls per process, every single turn) — no Redis/memory cache, no TTL.
- **No image/OCR support in file extraction.** Only CSV/XLS/XLSX/ODS/PDF/HTML/JSON/RTF/plain-text are handled; images (screenshots of a printed PO, etc.) fall into "unsupported format."
