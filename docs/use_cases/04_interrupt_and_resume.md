# UC-4: Interrupt an active process with a new one (park, then auto-resume)

User starts a new intent while another is still active/mid-form. The active node is parked (`paused`), the new one becomes active and is parented to it. Once the interrupting node finishes — completes, or is abandoned/cancelled — context automatically resumes to its nearest still-open (`active`/`paused`) ancestor: no click, no continuing message needed. A further, genuinely new request made from that resumed point becomes a new **sibling** of the node that just finished, not nested under it.

## Scenario

```
User starts a process:
"Quiero crear una solicitud de compra"
"La fecha requerida es 2026-09-01"
(process is now active, mid-form, node "1#0")

...but then interrupts it to start a new one:
"Listame los proveedores"

...and, after that resolves and control returns to the paused Purchase Request,
interrupts it again with a different side-query:
"Listame los artículos que contengan 'reclutamiento'"
```

## Preconditions

Turns 1-2 from UC-1 already happened: `active_node_id: "1#0"`, `intention_nodes: {"1#0": {status: "active", form_state: {RequriedDate: "2026-09-01"}, ...}}`.

## Turn-by-turn trace

### Turn 3 — "Listame los proveedores" (the interrupt)

**`agent-intent-finder.json`:**
- `Prompt: Intention Focus` builds the `INTENTION TREE` from `intention_nodes` — one node, `"1#0"`, status `active`, with `missing_required_fields` computed from its schema. This runs **before** `Agent: Find`.
- `Agent: Intention Focus` reads the tree + the new message + conversation memory: the message is entirely unrelated to the open Purchase Request form → returns a `focus` statement saying the user is pursuing something else (a side-step, not a continuation).
- `Prompt: Find` includes this as a `"USER'S CURRENT FOCUS"` block above the `INPUT JSON`.
- `Agent: Find`: per its own systemMessage, *"Trust that determination directly instead of re-deriving it yourself: if FOCUS says the user is pursuing something else, classify as 'new_intent', not 'pending_reply'"* — so it classifies `{"status": "new_intent", "new_intent_status": "match", "processes": [{"path": "purchase/vendor_list/vendor_list.json", "process_name": "List Vendors"}]}` even though node `"1#0"` is still open. (This FOCUS hand-off is what actually makes the interrupt work correctly — it also quietly compensates for a bug in `Agent: Find`'s own STEP 1, which checks a root-level `process_id`/`form_state.ready` that doesn't exist in the current state shape; FOCUS overriding the status decision means that broken check is never the deciding factor on this path.)
- `Compute Route Key`: `new_intent` + `match` → **`route_key = 'sap_form_filling'`**.

**`intent-manager.json`** — the park itself:
- `Already Delivered?` false.
- `Needs Park Before New?`: `status==='new_intent' && new_intent_status==='match' && Boolean(active_node_id)` — `active_node_id = "1#0"` → **true**.
- **`Park Current Intent`**:
  ```js
  const activeNode = nodes["1#0"];              // status: 'active'
  const shouldPause = activeNode.status === 'active';   // true
  intentionNodes = { ...nodes, "1#0": { ...activeNode, status: 'paused' } };
  const newParentId = findOpenAncestor("1#0");  // "1#0" itself is non-terminal -> returns "1#0" directly
  return { ..., active_node_id: null, new_process_parent_id: newParentId, intention_nodes: intentionNodes };
  ```
  No `form_state` snapshot needed — `intention_nodes["1#0"].form_state` is already the only copy that ever existed, so pausing is just a `status` flip. `new_process_parent_id` is a one-shot signal, consumed (not spread through) by `Prepare Node Registration` next. `findOpenAncestor` walks past any node already terminal (`completed`/`abandoned`) in the chain starting at `active_node_id` — irrelevant here since `"1#0"` is still `active`, but this is exactly what makes a *later* interruption (see turn 5 below) correctly skip past an already-finished sibling instead of nesting under it.

**`context-update.json`:**
- Resolves the "List Vendors" schema (3-tier GitHub cascade, same as UC-1).
- `Which Flow?` true → `Execute Workflow: Error Parser` (called directly — see the README's error-gate note): schema resolved cleanly → `Was Handled?` false → **`Prepare Node Registration` → `Execute Workflow: Register Intention Node`** (the shared `register-intention-node.json` sub-workflow, see UC-2):
  ```js
  const newNodeId = `${processId}#${Object.keys(priorNodes).length}`;   // priorNodes = {"1#0": {...}} -> length 1 -> e.g. "2#1"
  intentionNodes["2#1"] = { id: "2#1", parent_id: "1#0", process_id: 2, process_definition: {...}, form_state: {}, status: "active" };
  active_node_id = "2#1";
  ```
  Note the id counter is **global**, not per-process-type — the `#1` reflects "1 node existed before this one," not "1st node of process type 2." `parent_id: "1#0"` is exactly `new_process_parent_id` from the park step — this is what makes the graph nest the interruption under the process it interrupted, instead of flattening every interruption into a sibling root.

**Result after Context Update:** `intention_nodes = {"1#0": {status: "paused", form_state: {RequriedDate: "2026-09-01"}}, "2#1": {status: "active", parent_id: "1#0", form_state: {}}}`, `active_node_id = "2#1"`.

**`Router` → `SAP: Process Form Filling` → `SAP: Inquiry Execution`** (List Vendors is a GET/query process with no required filters — `Agent: Form` auto-confirms immediately per its GET rule; see UC-9 for the detailed GET trace). Once it completes, `Compute Execution Outcome` runs:
```js
intentionNodes["2#1"] = { ...node, status: "completed", process_definition: { name: "List Vendors" } };
const resumeTargetId = findResumeTarget("1#0", intentionNodes);  // "2#1".parent_id -- "1#0" is 'paused', non-terminal -> returns "1#0" immediately
intentionNodes["1#0"] = { ...intentionNodes["1#0"], status: "active" };
active_node_id = "1#0";
reset_process = true;
```
The interrupting node's own completion auto-resumes context back to the node it interrupted — no click, no continuing message needed.

**Final state after turn 3:** `active_node_id: "1#0"`, `intention_nodes: {"1#0": {status: "active", form_state: {RequriedDate: "2026-09-01"}, ...}, "2#1": {status: "completed", parent_id: "1#0", ...}}`. The sidebar shows the Purchase Request active again, with the completed List Vendors nested under it as a child — the conversation can continue the Purchase Request form directly, no extra step required.

### Turn 4 — a further side-query interrupts the (now-resumed) Purchase Request again

"Listame los artículos que contengan 'reclutamiento'" — same mechanism as turn 3: `active_node_id` is `"1#0"` (genuinely `active`, since turn 3's resume already reactivated it), so `Park Current Intent` pauses it again and hands its id forward as `new_process_parent_id`. `Register Intention Node` mints `"3#2"` with `parent_id: "1#0"` — **not** `parent_id: "2#1"`. Once this List Items query completes, `Compute Execution Outcome`'s resume walk starts at `"3#2".parent_id` (`"1#0"`, still `paused`) and resumes there directly.

**Final state after turn 4:** `active_node_id: "1#0"`, and the graph now shows `"2#1"` (List Vendors) and `"3#2"` (List Items) as **siblings**, both children of `"1#0"` — not `"3#2"` nested under `"2#1"`. This is the shape the whole mechanism exists to produce: every interruption attaches to whatever it actually interrupted, never to a sibling that merely happened to run most recently.

## How the resume happens — one algorithm, four call sites

Every place a live intention node can reach a terminal state (`completed` via a successful outcome, or `abandoned` via cancellation/an unrecoverable auth error) runs the same walk before delivering its reply:

```js
const TERMINAL_STATUSES = new Set(['completed', 'abandoned']);
const findResumeTarget = (nodeId, nodes) => {
  let current = nodeId;
  while (current) {
    const node = nodes[current];
    if (!node) return null;
    if (!TERMINAL_STATUSES.has(node.status)) return current;
    current = node.parent_id;
  }
  return null;
};
```

Starting from the finishing node's own `parent_id` (not the node itself), it walks upward past any ancestor that's *also* already terminal, and reactivates (`status: 'active'`) the first one that isn't. If nothing open is found anywhere up the chain, `active_node_id` resumes to `null` — genuinely nothing left to return to. `reset_process: true` always accompanies this, so Django's resettable merge (`main.py`'s `_merge_field`) actually applies an explicit `null` instead of coalescing it back to whatever was already in Redis.

The four call sites, each a duplicated copy of the same ~10-line function (deliberately not extracted into a shared sub-workflow — see each file's own comment for why):
- `sap-inquiry-execution.json` → `Compute Execution Outcome`, on a successful GET/POST outcome (this doc's own trace).
- `sap-process-form-filling.json` → `Compute Form Outcome`, on the `cancelled` branch (the user abandons a form mid-fill).
- `error-parser.json` → `Classify & Store Error`, on `AUTH_ERROR` (an unrecoverable auth failure abandons whatever was active).
- `batch-processing.json` → `Resolve Final State`, once every record in a batch turn has been processed and registered, walking from `new_process_parent_id` (what the batch itself interrupted).

`Park Current Intent` (`intent-manager.json`) runs the *exact same* walk for a different reason: at the moment a *new* interruption arrives, it needs the nearest still-open ancestor of whatever `active_node_id` currently is, to use as the new node's `parent_id`. In the normal case this is a single hop (since resume-on-completion keeps `active_node_id` accurate), but it stays defensive — walking past a stale terminal node it happens to still be pointed at, rather than assuming resume always ran first.

Resuming a node the user genuinely walked away from mid-conversation (rather than one that auto-resumed moments ago) is still possible via the sidebar — see **UC-6** — but that path is now only needed for a node whose *own* interrupting child hasn't finished yet, or for jumping to a non-immediate-ancestor node the auto-resume walk wouldn't reach on its own (e.g. a sibling branch entirely).

## Spec test outline

Closest existing models: `workflow/tests/integration/active_node_switch_django_direct_test.py` (UC-6's Django-direct mechanism, not this doc). For the park + resume mechanism itself:

- **Tier 1**: `workflow/tests/cases/unit/park-current-intent.json` covers the genuinely-active-gets-paused case, the already-terminal-just-gets-walked-past case (both `completed` and `abandoned`), and the chain-of-terminal-ancestors regression. `workflow/tests/cases/unit/compute-execution-outcome.json`, `compute-form-outcome.json`, `classify-and-store-error.json`, and `resolve-final-state.json` each cover their own call site's resume walk directly — a paused immediate parent, a terminal parent with an open grandparent further up, and the nothing-open-anywhere → `null` case.
- **Tier 2** (`path_intent_manager.json`): the "new_intent/match parking" and "new_intent/match right after a GET-style inquiry completed" cases cover both branches of `Park Current Intent` above. Model any new case on those rather than writing from scratch.
- **Tier 2** (`path_context_update.json`): assert `Execute Workflow: Register Intention Node`'s output has the new node's `parent_id` set to the just-parked node's id, and that `intention_nodes` retains the parked node with `status: "paused"` (not deleted, not merged) — the existing "while `new_process_parent_id` is set" case already covers exactly this.
- **Tier 2** (`path_sap_inquiry_execution.json`): a "success with a paused parent" case should assert the full round trip at the node level — `active_node_id` switches to the parent, the parent's own status flips back to `active` — live, without needing the full spine.
- **Live E2E**: send the 4 real turns above, assert via `load_current_state` that after turn 3, `active_node_id === "1#0"` (resumed, not `"2#1"`), `intention_nodes["1#0"].status === "active"` (reactivated), `intention_nodes["2#1"].status === "completed"`; after turn 4, `intention_nodes["3#2"].parent_id === "1#0"` (a sibling of `"2#1"`, not its child).
