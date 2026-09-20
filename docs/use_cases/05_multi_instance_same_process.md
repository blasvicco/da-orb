# UC-5: Multiple instances of the *same* process in one message

Two or more instances of the same process requested in one message (e.g. two purchase requests for different vendors). Handled by the same batch mechanism as UC-2 — `Agent: Find` returns one process, `Agent: Extract Batch Records` yields multiple records, each becoming its own Intention Graph node.

## Scenario

```
User initializes the chat with:
"Crea 2 solicitudes de compra separadas: la primera para el proveedor V10000 con fecha
requerida 2026-09-01, la segunda para el proveedor V20000 con fecha requerida 2026-09-15"
```

## Why this is its own doc, not folded into UC-2

This scenario is handled entirely by the same batch mechanism as UC-2 — requesting N instances of one process is architecturally identical to requesting instances of N different processes; the only difference is `Agent: Find` collapsing them into a `processes` array of length 1 instead of length 2+. This doc exists to make that explicit and give it its own spec-test anchor.

## Preconditions

None — fresh session (also works identically as a batch triggered mid-conversation, as long as `Agent: Find` classifies the message as `new_intent`/`batch`, not `pending_reply`).

## Turn-by-turn trace

**`agent-intent-finder.json`:**
- `Agent: Find`: this is the **literal example** in its own systemMessage's batch rule (*"e.g. 'crea 2 solicitudes de compra: ...'"*) → `{"status": "new_intent", "new_intent_status": "batch", "processes": [{"path": "purchase/purch_request/purch_request.json", "process_name": "Purchase Request"}]}` — **one** entry in `processes`, because both requested instances are the same distinct process type (*"two purchase requests written inline is still ONE entry in `processes`"*). Extracting the two records' actual field values is explicitly not this agent's job.
- `Compute Route Key` → **`route_key = 'batch_processing'`**.

**`intent-manager.json`:** no park (assuming nothing else was active).

**`context-update.json`:** resolves the **one** Purchase Request schema once (not twice), then — since `route_key === 'batch_processing'` — runs **`Agent: Extract Batch Records`** once for it (see UC-2's architecture note). Per its systemMessage, "identify every separate record the user wants to create for this process" — reads the full message, recognizes **two** separate records (different supplier, different date each), and returns `{"records": [{"Supplier": "V10000", "RequriedDate": "2026-09-01", ...}, {"Supplier": "V20000", "RequriedDate": "2026-09-15", ...}]}` — field-id-keyed `form_state` for each, not a submitted payload. `Build Intents`: `intents: [{path, process_definition, error: null, items: [<record 1>, <record 2>]}]` — one intent, two pre-resolved records. `Which Flow?` false (`batch_processing`) → no node registration *here* — same as every other batch path — but this is exactly the scenario per-record registration exists for: both requested instances still come from the **same one intent**, so it's `batch-processing.json`'s own per-record registration, not this file, that gives each of the two purchase requests its own node.

**`Router` → `Batch Processing` → `batch-processing.json`:** thin loop only, no agent (see UC-2). `Fan Out Intents` (which reads the intent back and flattens straight to per-record work items in one pass) → 2 work items → each flows through `Prepare SAP Inquiry Call` → `Execute Workflow: SAP Inquiry Execution` (`mode: "each"` — calls the real `sap-inquiry-execution.json`, which calls `sap_entity_create` once per record) → `Record Execution Result` → `Group Results By Intent` (groups both records' outcomes back under the one Purchase Request intent) → `Compose Batch Summary`: `"**Ejecución por lotes completada**\n- Purchase Request: 2 creadas, 0 fallidas"` → the shared registration pass (`Check Registration Needed`, which fans out directly into per-registration items → one `Execute Workflow: Register Intention Node` call registers both records) → `Resolve Final State` (auto-resumes `active_node_id` to whatever this turn interrupted, if still open — see UC-2/UC-4) → `Execute Workflow: Response` → Django callback. `state.intention_nodes` carries a real entry per record submitted — **both created purchase requests appear in the Intention Graph sidebar**, independently.

**Final state:** `intention_nodes` gains **two** new entries, one per record (`CardCode: "V10000"` and `CardCode: "V20000"`, each its own `purchase_request#N`) — this is the canonical case per-record (not per-intent) registration exists for: the two requests came from one intent, but each is independently clickable/correctable if it failed, without disturbing the other. `active_node_id` stays `null` for a fresh session. Delivered message still reports 2 created.

## Failure-mode note

The current, correct behavior for "N instances of one process" is exactly the batch path traced above, identical in shape to UC-2's "N different processes" — see that doc's failure-mode asymmetries (per-intent resolution-error tolerance vs. whole-batch agent-failure abort), which apply here too, except there's only ever one intent so the "tolerate one bad intent, continue the rest" behavior doesn't have a second intent to fall back to — a resolution failure or extraction failure here means the *entire* request fails (there's nothing else to fall back on), while a per-record failure among the extracted records (e.g. record 2's payload gets rejected by SAP) still reports record 1 as `"completed"` and record 2 as `"failed"` in the same summary.

## Spec test outline

Closest existing model: `workflow/tests/cases/unit/compose-batch-summary.json`'s first case already covers "2 items from 1 intent" at the summary-text level. For the classification step specifically:

- **Tier 1**: no direct unit test for `Agent: Find`'s classification exists (it's an LLM call, not a pure code node) — this is inherently a Tier 2/live-E2E concern, not Tier 1. `workflow/tests/cases/unit/prompt-extract-batch-records.json` covers the CREATE-side extraction prompt.
- **Tier 2** (`path_agent_intent_finder.json`): pin `Agent: Find`'s output to the exact 1-entry-`processes`/`batch` shape shown above, assert `Compute Route Key` → `route_key: "batch_processing"`. This is the regression guard for "same process, multiple instances" specifically — it should NOT produce `route_key: "sap_form_filling"` (which would mean only the first instance ever gets created) and it should NOT produce a 2-entry `processes` array (that would mean `Agent: Find` is treating the two instances as different processes, which is also wrong).
- **Tier 2** (`path_context_update.json`): pin `Agent: Extract Batch Records` to return 2 records for the single intent, assert `Return Context Update Result`'s `intents[0].items` has both.
- **Tier 2** (`path_batch_processing.json`): a pre-resolved 2-record intent, asserting `Resolve Final State`'s `intention_nodes` gained two distinct entries (this exact case already exists — "a create intent with 2 pre-resolved records").
- **Live E2E**: send the real message above, poll for delivery, assert the summary text reports 2 created, and assert `intention_nodes` gained **two** new entries, one per record, each with its own distinct id and the right `CardCode` in its own `form_state` (not one shared entry, not a collision between the two). Real SAP writes, so budget for cleanup/test-data awareness the same way `workflow/tests/integration/batch_execution_test.py`'s docstring already flags for its own (stale) equivalent.
