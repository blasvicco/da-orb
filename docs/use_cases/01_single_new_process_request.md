# UC-1: Single new process request (baseline)

The baseline flow: one SAP action, nothing else in play. Every other use case varies or interrupts this one, so its trace is written in full; the rest reference it instead of repeating the shared parts.

## Scenario

```
User initializes the chat with:
"Quiero crear una solicitud de compra"
(then, over one or more follow-up turns, supplies the required fields until the form is complete)
```

## Preconditions

None. Fresh session, `active_node_id: null`, `intention_nodes: {}`.

## Turn-by-turn trace

### Turn 1 — "Quiero crear una solicitud de compra"

**`spine.json`**
1. `Webhook` receives the POST body.
2. `Capture Root Execution` stamps `body._root_execution_id = $execution.id`.
3. `Context Enrichment` → `context-enrichment.json`:
   - `Enrich Context`: adds only what n8n itself needs to compute — the fixed `github_owner`/`github_repo` and a runtime `current_date`. Everything else passes through **completely untouched**: no trimming, no defaulting, no stripping, no bounds-checking of anything — that's not this workflow's job. The backend sends it only the data it needs, already clean and already valid, and nothing else. Both `language` and `expertise_level` are never defaulted or normalized here — the frontend sends the user's current UI locale and SAP expertise level on every single turn (either can change mid-conversation, via the language switcher or the expertise slider), so both are always present and valid by the time they reach here; a missing or out-of-range value would be an upstream bug to fix at the source, not something for this node to paper over. This node has no allowlist/denylist of its own and doesn't need one — the payload arrives already exactly right because it's curated at its actual source: the WebSocket message the frontend sends is validated by `SMessageSend` (`app/backend/web_socket/serializers/chat.py`), a strict contract that *rejects* any field it doesn't declare and requires both `language` and `expertise_level` (bounded to 1-3) outright. From that already-clean state, Django's `N8nClient.fire()` (`app/backend/web_socket/helpers/n8n/client.py`) builds the outgoing n8n payload field by field rather than forwarding anything verbatim, sending the workflow only the fields it actually reads — and nothing more. `active_node_id`/`intention_nodes` pass through exactly as sent (both empty this turn).
   - `Execute Workflow: File Extraction Core` → `file-extraction-core.json`: `bucket_file_ids` is empty → `Has Files?` false → `No Files: Passthrough` → `extracted_files: null`. Fast no-op, no HTTP calls.
4. `Agent: Intent Finder` → `agent-intent-finder.json`:
   - `Prompt: Intention Focus` builds an empty `INTENTION TREE` (`intention_nodes` is `{}`) → `Agent: Intention Focus` has nothing to focus on → `focus` comes back empty/null (fresh session).
   - `Status Text: Finding` / `Status: Finding` broadcast an ephemeral `"Interpretando mensaje..."`-style status to the WS group (never persisted, never affects state).
   - `Prompt: Find` builds `INPUT JSON` with `active_node_id: null`, `intention_nodes: {}`.
   - `Agent: Find`: no process is active → only `new_intent`/`general_inquiry` are valid. Classifies as `{"status": "new_intent", "new_intent_status": "match", "message": null, "processes": [{"path": "b1s/standard/purchasing/purchase_request_create.json", "process_name": "Create Purchase Request"}]}` — `path`/`process_name` are copied verbatim from the matched entry in `b1s/index.json` (`da-orb-processes` repo), never guessed or slugified by the agent itself. `message` here is the agent's *own* reply text (never the user's input) — it's only populated for `no_match`/`error`, to ask a disambiguation question or say it didn't understand; on a clean `match` like this one there's nothing to say yet, so it's `null`. The actual next message to the user (asking for the first form field) is built two steps later, by `Agent: Form` in `sap-process-form-filling.json`.
   - `Agent: Find`'s output (success or error alike) goes straight into `Merge Context: Find` (a `Set` node, `mode: raw`, merging `Prompt: Find`'s own pre-call context back in — an Agent node's output otherwise replaces the item entirely) → **`Execute Workflow: Error Parser`** (the shared `error-parser.json`, called unconditionally right after the agent — see the README's error-gate note and UC-11): no `error` field on a clean reply → its internal `Has Error?` gate takes the false branch, parses `output` into `_parsed` and hands control back. → `Was Handled? (Agent)` false → `Compute Route Key`: `status === 'new_intent'` and `new_intent_status === 'match'` → **`route_key = 'sap_form_filling'`**. `processes` survives the spread (`...restContent`) onto the output.
5. `Intent Manager` → `intent-manager.json`:
   - `Already Delivered?`: `route_key !== null` → false.
   - `Needs Park Before New?`: `status==='new_intent' && new_intent_status==='match' && Boolean(active_node_id)` — `active_node_id` is `null` → **false**. Nothing to park. Passes through unchanged.
6. `Context Update` → `context-update.json`:
   - `Needs Resolution?`: `processes.length > 0` → true.
   - `Fan Out Processes` turns the 1-entry `processes` array into 1 n8n item: `{...base, path: "b1s/standard/purchasing/purchase_request_create.json", process_name: "Create Purchase Request", items: []}`.
   - `Loop Over Processes` (batch size 1) → `Execute Workflow: Schema Resolution` → **`schema-resolution.json`** (full trace below) → resolves the real `process_definition` → `Record Result` → loop drains (1 item) → `Build Intents` collects `intents: [{path, process_name, process_definition, error: null, error_message: null, items: []}]`.
   - `Which Flow?`: `route_key === 'sap_form_filling'` → true → **`Execute Workflow: Error Parser`** (called directly — see the README's error-gate note): schema resolved cleanly, no `error` set → false branch → `Was Handled?` false → **`Prepare Node Registration` → `Execute Workflow: Register Intention Node`** (the shared `register-intention-node.json` sub-workflow — also the one `batch-processing.json` calls, see UC-2):
     - `processId = intent.process_definition.id` → `1`.
     - `newNodeId = "1#0"` (`` `${processId}#${Object.keys(priorNodes).length}` `` — 0 prior nodes).
     - `intention_nodes["1#0"] = {id: "1#0", parent_id: null, process_id: 1, process_definition: {...}, form_state: {}, status: "active"}`.
     - `active_node_id = "1#0"`.

**`schema-resolution.json`** (invoked once, inside Context Update's loop):
1. `Compute Schema Paths` derives 3 candidate paths from `path = "b1s/standard/purchasing/purchase_request_create.json"` (`pathPrefix="b1s"`, `module="purchasing"` — read from `base.module` if the caller set it, else the path's own second-to-last segment — `filename="purchase_request_create.json"`), `org = "bvs"`, `db = "BVS_SA_NEW_16062025"`:
   - `standard_path = "b1s/standard/purchasing/purchase_request_create.json"` (`base.path`, unchanged)
   - `org_standard_path = "b1s/bvs/standard/purchasing/purchase_request_create.json"`
   - `database_path = "b1s/bvs/BVS_SA_NEW_16062025/purchasing/purchase_request_create.json"`
2. `Fetch DB Override` (GitHub Contents API, `neverError: true`) → 404, no db-specific override exists for this org/process → `Has DB Override?` false.
3. `Fetch Org Override` → **200** — `bvs` genuinely overrides this process in the real `da-orb-processes` repo (adds mandatory `Supplier`/`TaxCode`/`CostingCode`/`CostingCode2` line fields that this org's SAP B1 instance enforces, bumped to `version: "1.4.0"` vs the driver-level `1.3.0`) → `Has Org Override?` **true** → routes straight to `Decode Process Definition`; `Fetch Standard` never runs this turn.
4. `Decode Process Definition`: base64-decodes, `JSON.parse`s the **org-level** content into `process_definition` (real shape includes `id`, `slug`, `name`, `form.sections[]`, `api.{service,endpoint,method}`, `confirmation`, `output`, `output_parsing`, `schema` slug reference), computes `schema_fetch_url` from the *winning* file's own directory — `b1s/bvs/standard/purchasing` here, since the org override is what actually resolved, not the driver-level standard dir — plus `process_definition.schema`.
5. `Fetch Schema` (unconditional) → 200 → `Decode & Set Schema`: merges `schema_definition` onto `process_definition`. Returns `{...original_trigger_input, process_definition, error: null, error_message: null}`.

No caching anywhere in this chain — 2 to 4 GitHub API calls depending which tier resolves (2 if the DB override itself hits, 4 if it falls all the way to standard); 3 in this trace, since the org override is what wins.

7. `Router`: `route_key === 'sap_form_filling'` → `SAP: Process Form Filling`.
8. `sap-process-form-filling.json`:
   - `Status Text: Collecting` / `Status: Collecting` broadcast `"Recopilando datos..."`.
   - `Prompt: Form` reads `intention_nodes["1#0"]` directly (object-key access, no root-level copy): `form_state = {}`, builds `FIELD STATUS` — every field `[PENDING]` since nothing is filled yet.
   - `Agent: Form`: the message gave no field values → `{"status": "in_progress", "message": "<asks for the header fields, e.g. Required Date>", "form_state": {}}`.
   - `Agent: Form`'s output → `Merge Context: Form` (same pre-call-context merge as `agent-intent-finder.json`'s `Merge Context: Find` above) → `Execute Workflow: Error Parser` → `Was Handled? (Agent)` false → `Compute Form Outcome`: `content.status === 'in_progress'` → `formState = {...{}, ...{}}` (no new values this turn) → mirrors into `intention_nodes["1#0"].form_state` (still `{}`) → `_should_execute: false`.
   - `Compute Form Outcome` → `Execute Workflow: Error Parser` (called again, unconditionally — this is the second, "outcome" gate site) → `Was Handled? (Outcome)` false → `Should Execute?` false → `Execute Workflow: Response`.
9. `response.json` → `Build Callback Payload` → POST to Django `n8n_callback`:
   ```json
   { "text": "<question asking for fields>", "type": "agent",
     "state": { "last_bot_message": "...", "active_node_id": "1#0",
                "intention_nodes": { "1#0": { "status": "active", "form_state": {}, "process_definition": {...} } } } }
   ```
10. Django `_resolve_and_persist_state` merges `active_node_id`/`intention_nodes`/`last_bot_message` into Redis; broadcasts to the WS group (frontend renders the agent reply + the sidebar now shows one node, "Create Purchase Request", active).

**State after turn 1:** `active_node_id: "1#0"`, `intention_nodes: {"1#0": {status: "active", form_state: {}, ...}}`.

### Turn 2 — "La fecha requerida es 2026-09-01" (repeat as needed per field)

Same spine path, but this time:
- `Agent: Find` sees `active_node_id: "1#0"` in `INPUT JSON` and the message plausibly continues the open form → `{"status": "pending_reply"}` → `Compute Route Key`: `pending_reply` → **`route_key = 'sap_form_filling'`** unconditionally (no sub-kind needed).
- `Intent Manager`: `Already Delivered?` false, `Needs Park Before New?` false (`status !== 'new_intent'`) → passthrough.
- `Context Update`: `Needs Resolution?` false (`processes` is absent/null on a `pending_reply` turn) → straight to `Return Context Update Result`, no schema fetch, no node registration (the node already exists).
- `SAP: Process Form Filling`: `Prompt: Form` now shows `RequriedDate` as the only thing to extract from the message; `Agent: Form` extracts `{RequriedDate: "2026-09-01"}` → `Compute Form Outcome` merges it into `intention_nodes["1#0"].form_state`.
- Repeats per field/turn until `Agent: Form` returns `{"status": "confirmed", "form_state": {...everything...}, "ready": true}` → `Compute Form Outcome` sets `shouldExecute = true`, mirrors `form_state.ready = true` → `Should Execute?` true → **`Execute Workflow: SAP Inquiry Execution`** (internal call, same execution, not via the Router).

### Final turn — SAP execution (`sap-inquiry-execution.json`, called internally from `sap-process-form-filling.json`)

1. `Status Text: Submitting` / `Status: Submitting` broadcast `"Enviando a SAP..."`.
2. `Build SAP Payload`: reads `intention_nodes["1#0"]`, `method = process_definition.api.method` (`POST`) → `operationType = 'POST_CREATE'`; walks `form.sections[]`, maps each field's `id` → `sap_field`, drops null/empty values, builds the SAP request body.
3. `Build Execution Prompt`: `POST_CREATE` branch → `chatInput` instructs `Agent: Execute` to call `sap_entity_create` with the exact payload.
4. `Agent: Execute` calls the SAP MCP tool once → `{"status": "success", "message": "<formatted success message with DocNum>"}`.
5. `Agent: Execute`'s output → `Merge Context: Execute` (same pre-call-context merge pattern, reading `Build SAP Payload`'s own output back in) → `Execute Workflow: Error Parser` → `Was Handled? (Agent)` false → `Compute Execution Outcome`: `status === 'success'` → `intention_nodes["1#0"].status = 'completed'` (form_state left as the submitted data, not cleared — its `ready` flag was already speculatively forced `false` by `Build SAP Payload`, see below; harmless here since a completed node's `ready` flag is never read again), `reset_process = true`. Then the auto-resume walk runs from `"1#0"`'s own `parent_id` — `null` here, since this is a fresh root process with nothing to interrupt — so `active_node_id` resumes straight to `null`. See UC-4 for the full mechanism, and for what happens instead when this same node *does* have a paused parent.
6. `Compute Execution Outcome` → `Execute Workflow: Error Parser` (the second, unconditional "outcome" gate call) → both outcomes converge directly on `Suppress Delivery?` (false for this direct, single-intent path — this turn never sets `suppress_delivery`, that only happens when `batch-processing.json` calls this same sub-workflow per record, see UC-2/UC-9) → `Execute Workflow: Response` → Django callback with the success message. (`Build SAP Payload`, back at the start of this trace, already forced `intention_nodes["1#0"].form_state.ready = false` speculatively before the outcome was even known; see UC-11.)

**Final state:** `active_node_id: null`, `intention_nodes: {"1#0": {status: "completed", form_state: {...submitted data...}}}`. Delivered message: `type: "agent"`, text includes the new SAP document number.

## Spec test outline

Closest existing models: `workflow/tests/integration/phase4a_intention_nodes_object_shape_test.py` (live E2E, same happy path) and Tier 1 cases `compute-form-outcome.json` / `compute-execution-outcome.json` / `prepare-node-registration.json` / `register-node.json` for the node-level pieces.

- **Tier 1** (fast, no live calls): pin `Agent: Find`'s output via `nodeResults` in a `path_agent_intent_finder.json`-style Tier 2 case, or unit-test `Compute Route Key`/`Prepare Node Registration`/`Register Node`/`Compute Form Outcome`/`Compute Execution Outcome` independently with hand-built `input` fixtures — this is what already exists and should stay the first line of defense for any change to this path.
- **Tier 2** (`workflow/tests/cases/integration/subworkflows/path_context_update.json`, `path_sap_process_form_filling.json`, `path_sap_inquiry_execution.json`): pin `Agent: Find`/`Agent: Form`/`Agent: Execute`'s outputs, assert `Execute Workflow: Register Intention Node`'s/`Compute Form Outcome`'s/`Compute Execution Outcome`'s node output shape without any real OpenAI/SAP calls.
- **Live E2E** (only needed when Tier 1/2 wouldn't catch a real regression, e.g. an actual prompt-wording change to `Agent: Find`/`Agent: Form`): send the real turns above against `/webhook/chat`, poll `load_current_state`/`get_messages` exactly like `phase4a_intention_nodes_object_shape_test.py`, assert:
  - after turn 1: `active_node_id` is a fresh `"<process_id>#0"` key present in `intention_nodes`, `form_state` empty/near-empty.
  - after each field turn: the just-supplied field appears in `intention_nodes[id].form_state`, nothing else changes.
  - after confirmation: `intention_nodes[id].status === 'completed'`, `active_node_id === null` (the auto-resume walk found no open ancestor — this is a fresh root process, see UC-4), delivered message mentions a document number.
