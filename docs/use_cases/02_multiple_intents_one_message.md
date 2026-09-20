# UC-2: Multiple distinct intents in one message

Two or more different SAP actions requested in one message. Handled by the batch path: a thin loop that reuses `sap-inquiry-execution.json` per record and registers one real Intention Graph node per record, not per intent.

## Scenario

```
User initializes the chat with:
"Quiero crear una solicitud de compra y también dar de alta un recibo de mercancía"
(= "I want to create a purchase request and also register a goods receipt")
```

### Architecture note: linear chain, no branch-then-reconverge

Three n8n behaviors, confirmed empirically, force this shape:

1. A node whose only input delivers zero items across an execution never runs — not "runs empty," skipped. So an intent with zero records still emits a `_skip_execution` marker instead of being omitted; `Check Registration Needed` likewise always emits at least a `{has_registrations: false}` placeholder.
2. A node fed by multiple graph connections runs once per connection that delivers data, not once combined. `Merge` (`mode: "append"`) hangs if one configured input is legitimately empty for that run.
3. `$('NodeName')` references are not execution-order dependencies. Referencing a non-ancestor node races; `.isExecuted` avoids a crash but not a stale read.

Consequence: every record's outcome and every unresolved intent converge through one linear path, never a branch that reconverges. Hard failures are tagged via `_hard_failure` inside `Record Execution Result` rather than routed by an upstream IF; `_skip_execution` markers flow through the same `Execute Workflow: SAP Inquiry Execution` call as real records.

Exception: two branches of the *same* IF node are mutually exclusive and safe to reconverge — `Has Registrations?`'s two outputs both feed `Resolve Final State` directly.

`sap-inquiry-execution.json` includes one guard for this: `Needs Real Execution?` IF checks `_skip_execution === true` and short-circuits to `Return SAP Inquiry Execution Result` unchanged — this doesn't affect any other caller of the sub-workflow.

Batch records are real, persisted Intention Graph nodes, registered via `register-intention-node.json` — one per record, same shared sub-workflow as UC-1's single-match path.

`Resolve Final State` auto-resumes an interrupted parent (same mechanism as UC-4's `sap-inquiry-execution.json`) — once every record in the batch is registered, `active_node_id` walks from `new_process_parent_id` to the nearest still-open ancestor and reactivates it, rather than leaving the parent `paused` waiting for a UC-6 sidebar click.

## Preconditions

None — fresh session.

## Turn-by-turn trace

### Turn 1 — the combined message

**`agent-intent-finder.json`:**
- `Agent: Find`: no active process → `new_intent`. Per its own rule, "a message mixing a purchase request and a goods receipt is TWO [entries]" → `{"status": "new_intent", "new_intent_status": "batch", "message": null, "processes": [{"path": "purchase/purch_request/purch_request.json", "process_name": "Purchase Request"}, {"path": "warehouse/goods_receipt/goods_receipt.json", "process_name": "Goods Receipt"}]}`. `processes` is one entry per distinct process type, never one per record — record-level detail is resolved downstream.
- `Compute Route Key`: `new_intent` + `batch` → **`route_key = 'batch_processing'`**.

**`intent-manager.json`:** `Needs Park Before New?` — `active_node_id` is `null` → false. No park.

**`context-update.json`:**
- `Needs Resolution?` true → `Fan Out Processes` → 2 items → `Loop Over Processes` (batch size 1) iterates twice, resolving each process's schema (see UC-1 for the 3-tier GitHub cascade), then — since `route_key === 'batch_processing'` — running `Agent: Extract Batch Records` for **each** process in that same iteration: Purchase Request extracts a create record from the message; Goods Receipt does the same for its own share of the message.
- `Build Intents` collects both into `intents: [{path, process_definition, error: null, items: [<extracted record(s)>]}, {...}]`.
- `Which Flow?`: false (`route_key !== 'sap_form_filling'`) → no node registration here — batch's nodes register later, inside `batch-processing.json`, once each record's real outcome is known.

**`Router`:** `route_key === 'batch_processing'` → `Batch Processing`.

**`batch-processing.json`:**
1. `Status Text: Batch Processing` / `Status: Batch Processing` broadcast once, before anything else.
2. `Fan Out Intents` (`$input.all()`, no loop) reads both intents back from `Status Text: Batch Processing`'s own item and flattens them straight into one combined list of per-record work items in one pass — 1 item for Purchase Request's record, 1 for Goods Receipt's. (An unresolved intent, or one that genuinely extracted zero records, would contribute one `_skip_execution` marker instead — see the architecture note above.)
3. Each work item flows through the same chain: `Prepare SAP Inquiry Call` → `Execute Workflow: SAP Inquiry Execution` (`mode: "each"`, the real `sap-inquiry-execution.json`, unmodified except for the `Needs Real Execution?` guard — its own `Build SAP Payload`/`Build Execution Prompt`/`Agent: Execute`/`Compute Execution Outcome` run exactly as they would for a single-match request, correctly branching POST_CREATE vs. GET_SINGLE vs. GET_QUERY on `process_definition.api.method` — this file never asks) → `Record Execution Result`, which restores the real `intention_nodes`/`active_node_id` the synthetic call temporarily replaced and produces either `_record_result: {form_state, status, message}` (success or graceful `SAP_ERROR`) or `_hard_failure: {error, error_message}` (anything else — a real agent/tool crash).
4. `Group Results By Intent` (`$input.all()`, the one aggregation point) groups every item back by `path`, builds each intent's own `items` array from its own records' `_record_result`s, and scans for any `_hard_failure` across the whole turn — if found, overrides `error`/`error_message` on every output item to the hard failure's own values.
5. `Has Any Hard Failure?`: true → `Execute Workflow: Error Parser (Agent Failure)` (reading the `error`/`error_message` `Group Results By Intent` already set) → `Execute Workflow: Response` — the whole turn aborts, same as a create's hard failure always has. False → `Compose Batch Summary`: `{...sharedContext, message: "**Ejecución por lotes completada**\n- Purchase Request: 1 creadas, 0 fallidas\n- Goods Receipt: 1 creadas, 0 fallidas"}` → `Check Registration Needed` (reads every intent's `_pending_registration` back via `$('Group Results By Intent').all()`, flattens them into one item per record — or a single `{has_registrations: false}` placeholder if there's nothing to register — tagging each with the shared `parent_id`) → `Has Registrations?` → true: one `Execute Workflow: Register Intention Node` call registers everything from the whole turn sequentially; false: the placeholder item carries no `intention_nodes` of its own — either way, both (mutually exclusive) branches converge directly into:
7. `Resolve Final State`: `new_process_parent_id`/`_pending_registration` are consumed (stripped, one-shot) — `new_process_parent_id` already did its job as every registration's `parent_id`, and is now also the starting point for the auto-resume walk: the nearest still-open ancestor of `new_process_parent_id` is found and reactivated, and `active_node_id` resumes to it (`null` if nothing was interrupted, or nothing open remains). `reset_process: true` always accompanies this, forcing the value through Django's resettable merge even when it's `null`. → `Execute Workflow: Response` → Django callback.

**Final state:** for a fresh session with two genuinely new creates (this doc's own scenario), `intention_nodes` gains two new entries, one per record actually submitted — `{"1#0": {process_id: 1, parent_id: null, status: "completed"|"failed", form_state: <submitted payload>}, "63#1": {...}}` (ids illustrative). `active_node_id` stays `null` — nothing was interrupted, so the resume walk from a `null` `new_process_parent_id` also resolves to `null`. If the batch had instead interrupted an active process, every new node would share that process's id as `parent_id`, and once registration finished, `active_node_id` would auto-resume to that parent (reactivating it) rather than leaving it stranded — see UC-4. Delivered message is the summary text; the sidebar shows real entries for what the batch just did, any failed one clickable per UC-6.

## Two documented failure-mode asymmetries (important for spec tests)

- **A schema-resolution or extraction failure for one intent is tolerated.** If "Goods Receipt" didn't resolve (bad path, 404 on GitHub) or its extraction agent failed, that intent contributes only a `_skip_execution` marker carrying its own `error`/`error_message` — `Group Results By Intent` still gives it its own entry (`items: []`), and `Compose Batch Summary` reports it as unresolved while Purchase Request still gets created: `"- Purchase Request: 1 creadas, 0 fallidas\n- Goods Receipt: no se pudo resolver (...)"`.
- **A live agent/tool failure aborts the *entire* batch.** If any single record's execution hits a hard failure (e.g. an LLM rate limit), `Group Results By Intent` detects it via `_hard_failure` and `Has Any Hard Failure?` routes straight to `Execute Workflow: Error Parser (Agent Failure)` → `Execute Workflow: Response`, bypassing `Compose Batch Summary` and the whole registration pass entirely. `Execute Workflow: SAP Inquiry Execution`'s `mode: "each"` runs every record sequentially regardless of an earlier one's outcome — a hard failure doesn't stop *remaining* SAP calls from happening, it only stops the turn from ever being registered or delivered normally once `Group Results By Intent` notices it. Nothing from a turn that hits this path gets registered — not even records that themselves succeeded — since registration only happens after the whole turn's outcome is known.

## Spec test coverage

Closest existing model: `workflow/tests/cases/integration/subworkflows/path_batch_processing.json` and `path_context_update.json` (Tier 2), plus `path_agent_intent_finder.json` for the classification step and `path_sap_inquiry_execution.json` for `suppress_delivery`/`mode: "each"`/the `Needs Real Execution?` guard.

- **Tier 1**: `fan-out-intents.json`, `record-execution-result.json`, `group-results-by-intent.json` are the load-bearing regression guards for the linear-chain design — in particular `group-results-by-intent.json`'s "two distinct intents, one record each" case is the regression guard against records leaking data across intents. `prompt-extract-batch-records.json`/`recover-state-extract-batch-records.json` (`context-update.json`) cover the extraction step. `register-node.json`, `check-registration-needed.json`, `resolve-final-state.json` cover the registration chain.
- **Tier 2** (`path_context_update.json`): batch-route cases assert `items` comes back populated with extracted records (not `[]`) for both a CREATE and a GET intent, plus an extraction-failure case surfacing via `error`/`error_message`.
- **Tier 2** (`path_batch_processing.json`): covers the flat pipeline — a single already-resolved record, an unresolved-intent-only turn (deliberately left unpinned, since the real `Needs Real Execution?` guard makes that safe and cheap), a mixed resolved+unresolved turn, a hard-failure abort, a GET-only intent, a mixed create+GET turn, a graceful `SAP_ERROR`, a multi-record create (proving N records mint N distinct nodes), a GET intent's own node carrying its extracted filter as `form_state`, an interrupted-parent turn (parent auto-resumes to `active` once the batch's registration finishes), and an all-unresolved turn. Several "mixed intents through the same pinned node" cases are documented fixture limits, not code gaps: a single static pin can't vary its output by which record is currently being processed, so two different intents sharing one pinned `Execute Workflow: SAP Inquiry Execution` call both end up with the pinned value's own identity — true multi-intent correctness is covered by Tier 1's `group-results-by-intent.json` and the live E2E test below, both of which use genuinely distinct data per intent.
- **Live E2E** (`workflow/tests/integration/batch_create_and_query_test.py`): sends a real "create a purchase request... and also list vendors" message, asserts `Agent: Extract Batch Records`' output inside the `Context Update` child execution, the delivered summary text, and `Resolve Final State`'s `intention_nodes` — cross-checked dynamically against the summary's own "N creadas, M fallidas" text. Specifically verifies the query intent's registered node carries its own extracted filter (`{"CardName": "Flete", "CardName_operator": "contains"}`), not the create intent's `form_state`.
