# UC-11: Error handling

Three distinct error shapes — SAP rejection, hard agent/tool failure, and auth error — all funneled through the shared `error-parser.json`, reached via different routes and left in different final states. UC-2's batch path depends on telling a graceful `SAP_ERROR` apart from everything else, so the distinction matters beyond this doc.

## Scenario A — SAP gracefully rejects a submission (e.g. missing required field)

```
Mid-form-fill, all fields the agent thought were required are confirmed, execution fires,
but SAP itself rejects it (e.g. a line item's required tax code is actually invalid).
```

`Agent: Execute` successfully called the tool — the LLM agent itself didn't fail, SAP just said no. This is a **graceful** error, not a hard node failure.

This flow goes through the shared `error-parser.json` gate (see the README's error-gate note for the full design): an unconditional `Has Error?` IF: `true` → `Classify & Store Error` → `Clear Route Key` (generic, harmless no-op for callers that don't use `route_key`) → returns; `false` → `Extract JSON` (parses the agent's raw output) → returns. Every caller invokes it **directly** after its own agent node (an Agent node's output otherwise replaces the item entirely, so a small `Set` node — `Merge Context: X` — re-merges the pre-call context back in first) and again, unconditionally, after its own outcome-computing node; the caller only ever checks `Boolean($json.error)` itself afterward (`Was Handled? (...)`) to decide whether to skip to delivery or keep going.

**Trace (`sap-inquiry-execution.json`):**
1. `Agent: Execute` returns `{"status": "error", "message": "<user-friendly explanation, possibly naming the offending field via FIELD REFERENCE>"}`.
2. `Merge Context: Execute` re-merges `Build SAP Payload`'s own pre-call context → `Execute Workflow: Error Parser`: `current.error` is **not** set (the agent didn't error, it replied normally) → its internal `Has Error?` gate takes the **false** branch → `Extract JSON` parses `output` into `_parsed`.
3. `Was Handled? (Agent)` **false** → `Compute Execution Outcome`:
   ```js
   } else {   // anything other than 'success'
     needsErrorParse = true;
     errorCode = 'SAP_ERROR';
     errorMessage = content.message;
     formState = { ...(formState || {}), ready: false };
     intentionNodes = { ...intentionNodesIn, [active_node_id]: { ...activeNode, form_state: formState } };   // node stays whatever status it had -- NOT marked completed or failed
   }
   ```
   (`Build SAP Payload`, before `Agent: Execute` ever ran, already speculatively forced this same node's `form_state.ready` to `false` — see Scenario B below. This branch's own `ready: false` is therefore redundant but harmless here — same value, set twice.)
4. `Compute Execution Outcome` → `Execute Workflow: Error Parser` again (the second, "outcome" gate call — unconditional): `error = 'SAP_ERROR'` → its internal `Has Error?` gate takes the **true** branch → `Classify & Store Error`: `rawError = 'SAP_ERROR'` (already `ALL_CAPS`, recognized as a known code, left as-is) → `message = error_message` override (the agent's own composed text survives verbatim, the generic `MSG` table is never consulted) → `clearState = false` (only `AUTH_ERROR` clears `active_node_id`) → `Clear Route Key` (no-op, this file never sets `route_key`).
5. Both of this gate call's outcomes converge directly on `Suppress Delivery?` — this specific call site needs no `Was Handled?` IF of its own, since the caller's very next step after this gate is the same node either way. `Suppress Delivery?` false → `Execute Workflow: Response` → `Build Callback Payload`'s type ternary:
   ```js
   type: (d.error && !['NO_MATCH', 'MULTIPLE_PROCESSES', 'AGENT_ERROR'].includes(d.error)) ? 'alert' : 'agent'
   ```
   `SAP_ERROR` is **not** in that soft-error exclusion list → **delivered as `type: "alert"`**, not a normal `agent` reply. (Contrast with `NO_MATCH`/`MULTIPLE_PROCESSES` from UC-10, which *are* excluded and deliver as plain `agent` messages — a real, meaningful distinction for anything on the frontend that styles alerts differently.)

**State after this turn:** node stays whatever `status` it had (typically `active`, since it was mid-confirmation), `form_state.ready` flipped back to `false`. `active_node_id` **unchanged** — still pointing at this node.

**Recovery (next turn, not same-turn):** per `Compute Execution Outcome`'s own comment, this is deliberate — *"No same-turn bounce-back to the caller... simpler and more robust to always deliver and let the next turn decide."* The user's next message is picked up as `pending_reply` (the node is still `active`, `form_state.ready` is `false`) → routes straight back into `sap-process-form-filling.json`. `Agent: Form`'s own rule explicitly supports a correction here: *"if the user's message provides a new value for one — including a value inherited from an earlier failed attempt at this same request — treat it as a correction and update it."* Once corrected and reconfirmed, `Should Execute?` fires again — a **fresh n8n execution**, not a loop inside the failed one.

## Scenario B — hard agent/tool failure (e.g. an LLM rate limit, a tool connection error)

```
Same mid-execution moment, but this time the LLM call itself fails (rate limit, timeout,
malformed tool response) rather than SAP gracefully rejecting a valid call.
```

**Trace:** `Agent: Execute`'s **error output** (`onError: "continueErrorOutput"`) fires instead of its normal output → `Merge Context: Execute` re-merges `Build SAP Payload`'s own pre-call context, folding the agent's raw error in alongside it → `Execute Workflow: Error Parser`: `$json.error` is set → its internal `Has Error?` gate takes the **true** branch → `Classify & Store Error`: `rawError` is now a **raw** error (e.g. `{message: "Rate limit exceeded, tokens per min"}`), not a pre-known code → text-pattern classified:
```js
: /rate.?limit|tokens.?per.?min|TPM|too.?large/i.test(errorText) ? 'RATE_LIMIT'
: /parse|json|syntax/i.test(errorText) ? 'PARSE_ERROR'
: /not.?found|404/i.test(errorText) ? 'NOT_FOUND'
: /unauthorized|403|401/i.test(errorText) ? 'AUTH_ERROR'
: /process.?loop/i.test(errorText) ? 'PROCESS_LOOP'
: 'UNKNOWN_ERROR';
```
`message` here comes from the generic `MSG` table (no `error_message` override this time — it's a raw system failure, not something an agent composed) → `Clear Route Key` (no-op, this file never sets `route_key`).

`Was Handled? (Agent)` **true** → `Suppress Delivery?` directly. `intention_nodes[active_node_id].form_state.ready` is already `false` by this point regardless: **`Build SAP Payload`, before `Agent: Execute` ever ran, speculatively forces this reset unconditionally** — harmless on the success path too, since `Compute Execution Outcome`'s success branch never reads `form_state.ready` (see UC-1). Node status is left untouched either way. `Suppress Delivery?` false → `Execute Workflow: Response` → delivered as `type: "alert"` (none of `RATE_LIMIT`/`PARSE_ERROR`/`NOT_FOUND`/`PROCESS_LOOP`/`UNKNOWN_ERROR` are in the soft-error list either).

**Recovery:** identical next-turn mechanism to Scenario A — `form_state.ready` is `false`, node stays `active`, next message is `pending_reply`.

## Scenario C — `AUTH_ERROR` specifically abandons the process

```
The SAP connection itself is invalid (expired session, bad credentials at the MCP-tool
level) -- a 401/403 surfaces in the raw tool/connection error text.
```

Same hard-failure path as Scenario B, but `Classify & Store Error` matches the `unauthorized|403|401` pattern → `error_type = 'AUTH_ERROR'` → **`clearState = true`**, which now runs the same auto-resume walk every other terminal-state transition uses (see UC-4), instead of unconditionally clearing to `null`:
```js
const clearState = error_type === 'AUTH_ERROR';
let activeNodeId = $json.active_node_id;
let intentionNodes = $json.intention_nodes || {};
let resetProcess = $json.reset_process === true;
if (clearState) {
  const activeNode = intentionNodes[$json.active_node_id] || {};
  const resumeTargetId = findResumeTarget(activeNode.parent_id, intentionNodes);   // walks up past completed/abandoned ancestors
  if (resumeTargetId) intentionNodes = { ...intentionNodes, [resumeTargetId]: { ...intentionNodes[resumeTargetId], status: 'active' } };
  activeNodeId = resumeTargetId;
  resetProcess = true;   // forces the value through even when it lands on null
}
return { ..., active_node_id: activeNodeId, intention_nodes: intentionNodes, reset_process: resetProcess, error: error_type };
```
`active_node_id` resumes to the nearest still-open ancestor of whatever this auth failure abandoned — reactivating it — or to `null` if nothing open remains anywhere up the chain. This runs after `Build SAP Payload` (in `sap-inquiry-execution.json`'s case) already ran its own unconditional `form_state.ready = false` reset against the *original*, still-set `active_node_id`, earlier in the same turn (see Scenario B). So the abandoned node's own entry in `intention_nodes` still only picks up that one `ready` flip — its own `status` is left exactly as it was (a known, pre-existing gap, not introduced by this fix: the node itself is never marked `abandoned` or `failed`, just orphaned from `active_node_id`).

**Recovery:** if a paused ancestor existed, the resume walk already reactivated it — the conversation can continue directly, no click needed. The abandoned node itself still exists in `intention_nodes`, orphaned (nothing points `active_node_id` at it), reachable only by clicking it in the Intention Graph sidebar — see **UC-6**.

## Cross-reference: the `last_error` gap

`general-inquiry.json`'s `Prompt: Context & Conversation` computes its own `last_error` **fresh, per-turn**, from the *current* `error` field plus a live scan for a `status: 'failed'` node — it does **not** read any round-tripped "last error" state; no such field exists in the persisted state (see the README's state-shape section). Note also: **none of the three scenarios above ever set a node's status to `'failed'`** — `Compute Execution Outcome`/`Build SAP Payload`'s own speculative reset only ever flip `form_state.ready`. So `Agent: Context & Conversation`'s `lastFailedNode` lookup (`nodeList.find(n => n.status === 'failed')`) will find **nothing** for any of these three error paths — a "what went wrong?" question only has something to reference if the *current* turn's own `error` is still set (i.e. asking immediately, same turn) or if some other, currently-unidentified code path actually sets `status: 'failed'` somewhere in this system (worth a follow-up grep if this matters for a real feature). See UC-8 for the fuller trace of this gap.

## Spec test outline

Closest existing models: `workflow/tests/cases/unit/classify-and-store-error.json` (Tier 1, covers the classification table directly) and `workflow/tests/cases/integration/subworkflows/path_sap_inquiry_execution.json` (Tier 2, likely already has an error case — extend rather than duplicate).

- **Tier 1** (`classify-and-store-error.json`): already covers `RATE_LIMIT`/`NOT_FOUND`/`AUTH_ERROR`/`UNKNOWN_ERROR` classification and the `AUTH_ERROR`-clears-`active_node_id` behavior. Add a case for `SAP_ERROR` as an already-known ALL_CAPS code specifically (proving it's never re-classified through the regex table even if its `error_message` text happens to mention "unauthorized" or similar).
- **Tier 1** (`compute-execution-outcome.json`): should already cover the graceful-error branch (`form_state.ready: false`, node stays whatever status). Add a case proving the node's `status` is genuinely untouched (not flipped to `failed`) — this is the fact UC-8's `last_error` gap depends on.
- **Tier 2** (`path_sap_inquiry_execution.json`): pin `Agent: Execute` to a graceful `{"status": "error", ...}` reply, assert `Build Callback Payload`'s `type: "alert"`. Separately, pin `Agent: Execute`'s **error output** to simulate a hard failure, assert the routing hits `Execute Workflow: Error Parser (Agent Failure)` (not `Compute Execution Outcome`) with `form_state.ready` already `false` (from `Build SAP Payload`'s own reset) and still ends at `type: "alert"`.
- **Tier 2**: a dedicated `AUTH_ERROR` case asserting `active_node_id: null` in the final callback `state`, while `intention_nodes[<the abandoned id>]` is still present, unmodified, in the same `state.intention_nodes` object — this is the fact UC-6's "still clickable later" recovery path depends on.
- **Live E2E**: hardest to simulate genuinely (can't easily force a real SAP rejection or a real rate limit) — if needed, use a deliberately invalid payload (e.g. omit a known-required field that `Agent: Form` might occasionally miss) and assert the delivered message is `type: "alert"` and a follow-up correction turn succeeds normally, proving the full round trip rather than just the classification logic in isolation.
