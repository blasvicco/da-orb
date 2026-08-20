# UC-9: Search/query (GET) process — single match, not batch

A single search/GET request (e.g. list vendors), classified and routed exactly like UC-1's create — the GET/POST distinction only matters once `sap-inquiry-execution.json` actually executes. This doc traces just that difference.

## Scenario

```
User initializes the chat with:
"Lístame los proveedores que contengan 'Flete' en el nombre"
(= "List me the vendors whose name contains 'Flete'")
```

A single GET/search request is routed and classified exactly like UC-1's POST/create request — `Agent: Find` doesn't know or care about GET vs. POST; that distinction only appears once execution actually happens, inside `sap-inquiry-execution.json`. This doc exists to trace the parts that genuinely differ.

See UC-2 for how a GET-type process is handled when it's one of *several* processes in a single batch-classified message — `batch-processing.json` calls **this exact sub-workflow**, unmodified except for a `Needs Real Execution?` short-circuit guard (see UC-2's architecture note; it never fires for this single-match path), via its `suppress_delivery` flag (below `Status: Submitting` in the node list, checked by `Suppress Delivery?`; skips this workflow's own Django callback so the caller can compose one combined reply instead) rather than reimplementing any of `Build Execution Prompt`'s filter-building logic — batch calls this once per record via `mode: "each"`, not once per turn. The only thing batch does differently is how `form_state` gets populated: a one-shot extraction agent (`Agent: Extract Batch Records`, running in `context-update.json`) instead of the multi-turn `Agent: Form` interview traced below, assembled into a throwaway single-entry `intention_nodes` just for that one call.

## Preconditions

None — fresh session. (⚠️ A request with **zero filters at all**, e.g. plain "listame los proveedores," is a real edge case — see the note at the end of this doc before writing a spec test around it.)

## Turn-by-turn trace

**`agent-intent-finder.json`:** identical shape to UC-1 — no active process → `Agent: Find`: `{"status": "new_intent", "new_intent_status": "match", "processes": [{"path": "purchase/vendor_list/vendor_list.json", "process_name": "List Vendors"}]}` (one process, `match` not `batch` — a single search request is one actionable thing, not "several things to do"). `Compute Route Key` → **`route_key = 'sap_form_filling'`** — same route as any single-match request; there is no separate GET-specific `route_key`.

**`intent-manager.json` / `context-update.json`:** identical mechanism to UC-1 — no park (nothing active), schema resolved via the same 3-tier GitHub cascade, `Prepare Node Registration` → `Execute Workflow: Register Intention Node` creates a new node. The fetched `process_definition` for a GET-type process has a different internal shape than a POST one — `api.method: "GET"`, a `query` block (`{key, filters, default_filters, select, top, order_by}`) instead of `form.sections`.

**`Router` → `SAP: Process Form Filling`:**
- `Prompt: Form`: since `process_definition.form?.sections` doesn't exist for a GET-only process, the `FIELD STATUS` loop produces zero `pendingLines`. The code specifically checks for this:
  ```js
  completionStatus = ((process_definition?.api?.method || '').toUpperCase() === 'GET' && Array.isArray(process_definition?.query?.filters) && process_definition.query.filters.length > 0)
    ? `  (no required form.sections fields -- this is a search/query process; see QUERY FILTERS below and check the CURRENT USER MESSAGE for filter values before deciding to confirm)`
    : `  (all fields complete — ready to confirm)`;
  ```
  and appends a dedicated `QUERY FILTERS FOR THIS SEARCH` block listing each declared filter as `[AVAILABLE]` or `[SET]`.
- `Agent: Form`: per its GET-specific rule (*"once the user's message specifies at least one filter... set status to confirmed immediately... do not ask about other optional filters the user did not mention"*) — the message already gives a usable filter (`name contains 'Flete'`) → `{"status": "confirmed", "form_state": {"CardName": "Flete", "CardName_operator": "contains"}, "ready": true}` immediately, no back-and-forth.
- `Compute Form Outcome`: merges into `intention_nodes[id].form_state`, `_should_execute = true` → `Should Execute?` true → internal call to `sap-inquiry-execution.json`.

**`sap-inquiry-execution.json` — where GET vs. POST actually branches:**
1. `Build SAP Payload`: `method = process_definition.api.method.toUpperCase()` → `"GET"`. `keyDef = process_definition.query.key` — nothing in `form_state` matches a specific key value (this is a filtered list, not a lookup-by-id) → **`operationType = 'GET_QUERY'`** (as opposed to `GET_SINGLE`, which fires when a `query.key` value *is* resolved — e.g. "show me vendor V10000").
2. `Build Execution Prompt`, `GET_QUERY` branch — this is the most involved code path in the whole system:
   - Builds an OData v2 filter expression from `form_state`: `CardName_operator = "contains"` maps through `STRING_FILTER_BUILDERS.contains` → `substringof('Flete', CardName)`.
   - Prepends any `process_definition.query.default_filters` (an intrinsic constraint of the process itself, e.g. `CardType eq 'cSupplier'` for a vendor-only list, distinct from Business Partners in general) — these are **always** ANDed in, never optional, never overridable by the user's own filter combination.
   - Multiple user-supplied filter values combine with **OR** by default (*"cast a wide net"*), **AND** only if the user explicitly says so (`form_state.match_all = true`).
   - Resolves `top`/`order_by`/`requested_fields` from `form_state`, falling back to the process definition's own defaults.
   - Full `chatInput` instructs `Agent: Execute` to call `sap_query_entity_set` with the assembled filter string, select list, top, and orderby.
3. `Agent: Execute` calls the tool once → returns a Markdown table (or a `no records` message — **both map to the same `{"status": "success", ...}` shape**; `Compute Execution Outcome` does not distinguish 0 records from N records at the code level, only via whatever free-text the LLM wrote).
4. `Compute Execution Outcome`: `status === 'success'` → `intention_nodes[id].status = 'completed'`, `reset_process = true`. Identical outcome handling to a POST success — this node never inspects `sap_operation` at all. Then the auto-resume walk runs from this node's own `parent_id`: `null` in this scenario (a fresh, standalone search, nothing interrupted), so `active_node_id` resumes straight to `null` — see UC-4 for what happens instead when this same node has a paused parent (it resumes there, reactivating it, instead).

**Final state:** one new `completed` node, holding the filter values it was searched with as its `form_state`; `active_node_id: null`. Delivered message: a Markdown table of matching vendors (or a "no vendors found" sentence).

## The zero-filter edge case (flagged, not resolved here)

`Agent: Form`'s systemMessage says: *"Only ask a clarifying question if the user gave no usable filter, limit, or field selection at all."* A bare "listame los proveedores" gives none of those. Whether the real behavior is "ask what to filter by" or "just list everything up to the default `top`" has **not been live-verified**. There's also a related, known contradiction for `expertise_level === 1` (Guided) GET requests: `[CONFIRMATION REQUIRED]` misfires unconditionally on turn one for a GET process at level 1, since `pendingLines.length === 0` is trivially true with no `form.sections`. **Verify live before writing a strict spec test asserting either behavior for the no-filter case.**

## Spec test outline

Closest existing model: `workflow/tests/cases/integration/subworkflows/path_sap_inquiry_execution.json` (already has GET_SINGLE/GET_QUERY cases) and `workflow/tests/integration/vendor_lookup_during_form_fill_test.py` (referenced elsewhere in this repo's test suite as the live-E2E model for a vendor-lookup side-query).

- **Tier 1**: `build-execution-prompt.js`-equivalent unit cases (check `workflow/tests/cases/unit/` for the actual file name) should cover: single-filter contains, multi-filter OR-by-default, multi-filter explicit AND (`match_all`), a filter combined with a process's own `default_filters`, and the operator-suffix parsing (`<field>_operator`). Extend rather than duplicate if these already exist in some form.
- **Tier 2**: pin `Agent: Form` to the confirmed shape above, assert `Build Execution Prompt`'s `chatInput` contains the expected OData fragment (`substringof('Flete', CardName)` plus the process's own `default_filters` ANDed in) — this is the highest-value regression guard in this whole use case, since the filter-building logic is by far the most complex code in the system.
- **Tier 2**: a dedicated case for the zero-filter edge (once live-verified) — whatever the confirmed real behavior turns out to be, pin it explicitly so a future prompt change can't silently flip it unnoticed.
- **Live E2E**: send the real message above, assert the delivered table only contains vendors matching the filter, and that `intention_nodes[id].form_state` records the filter that was actually used (useful for a later "what did I search for" general-inquiry question — see UC-8).
