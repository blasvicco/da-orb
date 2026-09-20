# UC-10: Ambiguous request needing clarification

A request that doesn't resolve to one process: either named ambiguity (several sibling processes match equally) or a genuinely unclear message. Both produce the same `no_match` shape and downstream path; only the reply text differs.

## Scenario

```
User initializes the chat with:
"Necesito ver los socios de negocio de Acme Corp"
(= "I need to see the business partners for Acme Corp" -- "socios de negocio"/"business
partners" is a generic term that could mean Vendors, Customers, or Leads, which are
separate processes in this system's index)
```

Two genuinely different flavors of "the request didn't resolve" exist in `Agent: Find`'s own classification, and they're handled identically downstream — worth distinguishing when writing a spec test:

1. **Named ambiguity** (this scenario): the request is clear and actionable, but multiple sibling processes' keywords all match equally and nothing in the message disambiguates which one. `Agent: Find` names the real candidates by their real `process_name`s and asks which one.
2. **Genuinely unclear**: a stray word, a likely typo, random characters, or something with no discernible SAP intent at all (e.g. "prover"). `Agent: Find` gives a generic, warm "I didn't understand" response instead of naming candidates it can't actually identify.

Both produce the exact same `new_intent_status: "no_match"` shape and take the exact same downstream path — only the `message` text differs.

## Preconditions

None required.

## Turn-by-turn trace

**`agent-intent-finder.json`:**
- `Agent: Find`: no active process → `new_intent`. Per its own rule for named ambiguity: *"Call GitHub MCP, load the process index, identify every candidate process this single request could plausibly mean, and write `message` naming those specific candidates by their real `process_name`... e.g. '¿Te referís a Proveedores, Clientes o Leads?'"* →
  ```json
  { "status": "new_intent", "new_intent_status": "no_match", "message": "¿Te referís a Proveedores, Clientes o Leads?", "processes": null }
  ```
- `Compute Route Key`:
  ```js
  } else if (status === 'no_match') {
    needsErrorParse = true;
    errorCode = 'NO_MATCH';
    errorMessage = content.message || null;
  }
  ```
  `route_key` is **never set** for this branch (stays `null`) — `no_match` does not go through the spine's `Router` at all; it's fully handled inside `agent-intent-finder.json` itself.
- `Compute Route Key` → **`Execute Workflow: Error Parser`** (called directly and unconditionally — the gate lives inside `error-parser.json` itself, see the README's error-gate note and UC-11): `error` is set → its internal `Has Error?` gate takes the true branch → `error-parser.json`'s `Classify & Store Error`:
  ```js
  const isKnownCode = typeof rawError === 'string' && /^[A-Z][A-Z_]*$/.test(rawError);   // 'NO_MATCH' is already ALL_CAPS -> true, left as-is
  const message = $json.error_message || MSG[error_type]?.[lang] || MSG.UNKNOWN_ERROR[lang];  // error_message override -> the agent's own composed question survives verbatim
  const clearState = error_type === 'AUTH_ERROR';   // false here
  return { ...$json, message, active_node_id: clearState ? null : $json.active_node_id, error: error_type };
  ```
  Since `error_message` was set by `Agent: Find` itself, the generic `MSG` table is never consulted — the delivered text is exactly what the agent wrote. `active_node_id` is left untouched (only `AUTH_ERROR` clears it).
  `error-parser.json`'s own true branch also nulls `route_key` before returning (a generic `Clear Route Key` step inside the shared gate) → `Was Handled? (Route)` true → `Execute Workflow: Response` → **this whole thing never leaves `agent-intent-finder.json`** — it returns straight to the spine's `Agent: Intent Finder` node, which then continues to `Intent Manager` per the spine's normal wiring... except `route_key` arrived as `null`, so:

**`intent-manager.json`:** `Already Delivered?`: `route_key === null` → **true** → straight to `Return Intent Manager Result`, skipping `Needs Park Before New?`/`Park Current Intent` entirely. This is exactly what "Already Delivered?" means — the reply was already sent (via `Execute Workflow: Response` inside `agent-intent-finder.json`, above) before this node ever runs; nothing downstream should touch state or fire again.

**`context-update.json`:** `Needs Resolution?` false (`processes` is `null`) → passthrough.

**`Router`:** never actually dispatches anywhere meaningful for this turn — by the time execution reaches here, the reply has already gone out and `route_key` is `null`, so the switch's `fallbackOutput: "extra"` sends it to `Unmatched Route (debug)`, a `noOp`. This is harmless (the callback already fired) but worth knowing if a spec test naively asserts "which Router branch fired" for a no-match turn — the answer is "none that matters; the debug branch is a no-op tail, not where the real behavior lives."

**Final state:** `active_node_id`/`intention_nodes` unchanged from before the turn. Delivered message: `type: "agent"` (`NO_MATCH` is in the soft-error list in `Build Callback Payload`'s ternary, so it's never delivered as `type: "alert"`), text = the disambiguation question.

## The "genuinely unclear" variant

Same mechanism exactly, different `Agent: Find` output:
```json
{ "status": "new_intent", "new_intent_status": "no_match", "message": "No logré entender tu mensaje, ¿podrías contarme qué necesitas hacer?", "processes": null }
```
Per the agent's own rule: *"a single friendly response, not the start of a forced back-and-forth -- don't ask a follow-up question that demands a specific structured reply."* Everything from `Compute Route Key` onward is identical to the named-ambiguity case above.

## Spec test outline

Closest existing model: `workflow/tests/cases/integration/subworkflows/path_agent_intent_finder.json` already has cases titled *"new_intent/no_match -&gt; classified via the shared Error Parser..."* and *"...actually reaches and calls Response for delivery"* — model any new case directly on those rather than writing from scratch.

- **Tier 1**: `compute-route-key.json` should have a `no_match`/`error` case asserting `route_key` is **absent** from the output (not `null` — Tier 1's strict harness needs the key omitted from `expected`, per the README's harness note) and `_needs_error_parse: true, error: "NO_MATCH"`.
- **Tier 2**: pin `Agent: Find` to each of the two `no_match` flavors (named-ambiguity vs. genuinely-unclear), assert `Execute Workflow: Error Parser (Route)`'s output `message` matches exactly what the agent composed (proving `error_message` overrides the generic table, per `Classify & Store Error`'s own logic). Also assert — this is the regression the existing test titled *"actually reaches and calls Response for delivery"* already guards — that `Execute Workflow: Response` genuinely runs for this branch.
- **Tier 2**: assert `Intent Manager`'s `Already Delivered?` branch fires (`route_key === null`) and neither `Needs Park Before New?` nor `Park Current Intent` run for this turn — useful as a "no_match never accidentally parks an active node" regression guard, especially relevant if this happens while another process is already active.
- **Live E2E**: send a genuinely ambiguous real message (something matching 2+ real process keywords in the live GitHub-hosted process index) and confirm `Agent: Find` names the *real* candidate process names from the index, not hallucinated ones — this can't be meaningfully pinned/faked since it depends on the live index content.
