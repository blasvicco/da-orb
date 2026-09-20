# UC-13: Cross-entity discovery (no cataloged process fits)

A legitimate, well-understood SAP question that no cataloged process — alone or in combination — can answer, because it needs data joined across two or more entities that no single process's fixed filter set reaches. Routes to a new, more autonomous sub-workflow (`sap-discovery.json`) instead of looping the user through `no_match`.

## Scenario

```
User asks:
"Qué proveedores nos proveen artículos del grupo no productivos?"
(= "Which vendors supply us items from the 'no productivos' group?")
```

This traces back to the original bug report that motivated the `resolve` feature (UC-9's autonomous name→code lookup): a user asking for vendors "del grupo no productivos" that turned out, on investigation, not to be a `BusinessPartnerGroup` at all — `no productivos` doesn't exist as any vendor/customer group name on the live tenant. It's a real `ItemGroups` entry instead (`Number: 100`, `GroupName: "No Productivos"`). The real question was always "which vendors supply items in this item group" — a genuine cross-entity join `vendor_list`'s own filters (`CardName`, `Currency`, the vendor's own `GroupCode`) can never reach, since it has no concept of "items this vendor supplies."

**A genuinely ambiguous phrasing note, confirmed via a live run:** "listame los proveedores que pertenezcan al grupo no productivos" (vendors *belonging to* group X) is NOT the same request as "qué proveedores nos proveen artículos del grupo no productivos" (vendors who *supply* group X) — the first phrasing superficially matches `vendor_list`'s own `GroupCode` filter (a vendor's own group), so `Agent: Find` correctly classifies it as `new_intent_status: "match"`, not `"discover"` — this is correct behavior, not a bug; `discover` is reserved for when nothing in the catalog fits at all. Only the second phrasing (asking what a vendor *supplies*, not what group a vendor *belongs to*) has no cataloged match.

## Preconditions

None required. Works from a clean slate; also works as a side-question while another process is active (see Statelessness below).

## Turn-by-turn trace

**`agent-intent-finder.json`:**
- `Agent: Find`: no cataloged process fits, the request is clear and read-only →
  ```json
  { "status": "new_intent", "new_intent_status": "discover", "message": null, "processes": null }
  ```
  Distinguished in the agent's own prompt from both `no_match` flavors: not named ambiguity (no candidate processes *could* answer this), not unclear (the request is fully understood). Reserved for lookups only — a write-shaped request with no cataloged match is still `no_match`, since `discover` hands off to a strictly read-only step.
- `Compute Route Key`:
  ```js
  } else if (status === 'discover') {
    route_key = 'sap_discovery';
  ```
  Mirrors the `match`/`batch` branches (dispatch-onward), not the `no_match`/`error` short-circuit path — this is the one case besides `match`/`batch` that actually reaches the spine's `Router`.
- `context-update.json`'s `Needs Resolution?` gate (`Array.isArray($json.processes) && $json.processes.length > 0`) is false (`processes` stays `null`) → passes straight through, no schema-resolution/registration side effects.
- `intent-manager.json`'s `Needs Park Before New?` only fires for `match`/`batch` → an in-progress process elsewhere is never parked or disturbed by a discovery side-question.

**`spine.json`:** `Router` dispatches `route_key === 'sap_discovery'` → **`SAP: Discovery`** (`sap-discovery.json`).

**`sap-discovery.json`:**
- `Build Discovery Prompt`: builds `chatInput` with the SAP connection, GitHub-catalog fetch instructions (index path `{organization.target}/index.json`), the OData v2 filter syntax rules, and the user's question — no fixed call specification the way `sap-inquiry-execution.json`'s `Build Execution Prompt` gets one; `Agent: Discover` plans its own chain.
- `Agent: Discover` — tools: `GitHub MCP` (`get_file_contents` only, ≤2 calls: the index, optionally one related schema's `fields`/`relations`) + `SAP MCP` (`sap_query_entity_set`/`sap_entity_get` only — `sap_entity_create` excluded at the tool-allowlist level, not just prompted against — ≤4 calls). Same resolution discipline as `resolve`'s `Agent: Execute`: a name→code lookup returning 0 or >1 matches stops the chain and replies gracefully rather than guessing.
- `Compute Discovery Outcome`: `status: "success"` (covers a full answer, a partial answer within budget, *and* a clean "nothing found") passes the message through; anything else becomes `SAP_ERROR`. No `intention_nodes` mutation at all — see Statelessness below.

## Statelessness

`SAP: Discovery` never creates or touches an `intention_nodes` entry — verified via Tier 2 fixture (`path_sap_discovery.json`'s first case): `active_node_id`/`intention_nodes` come out **byte-identical** to input, even with a genuinely unrelated in-progress process sitting there. Mirrors `general-inquiry.json`'s pattern, not `sap-inquiry-execution.json`'s — there's no cataloged process identity to hang a resumable node on, and the whole point of this flow is "no multi-turn form, answer and done."

**Known trade-off, not a bug:** because there's no `intention_nodes` entry, a discovery turn that asks the user to disambiguate (e.g. "I found 2 matching groups, which one?") cannot be resumed as a `pending_reply` the way a cataloged process's mid-form turn can — a bare follow-up reply like "101" has nothing to attach to and would be reclassified fresh by `Agent: Find` from conversation memory alone (`last_bot_message`/FOCUS), not guaranteed to reconnect correctly. Confirmed live: this exact scenario happened unprompted during testing (see below) — the agent found two `ItemGroups` rows matching the same name (a genuine, previously-unknown data collision: `Number: 101, GroupName: "BIENES"` and `Number: 165, GroupName: "Bienes"`) and asked the user to pick, correctly refusing to guess.

## Final state

`active_node_id`/`intention_nodes` unchanged from before the turn (see Statelessness). Delivered message: `type: "agent"` on success (including a graceful "nothing found" or "ambiguous, please clarify" outcome), `type: "alert"` only on a genuine `SAP_ERROR`/hard agent failure.

## Spec test outline

- **Tier 1**: `compute-route-key.json` has a `discover → route_key sap_discovery` case plus a message-survival regression case, mirrored on the existing `match` case. `build-discovery-prompt.json` (connection-shape cases, `github_tag` default), `compute-discovery-outcome.json` (success/error/unparseable), `status-text-discovering.json` — all new, one file per node, same convention as every other sub-workflow.
- **Tier 2**: `subworkflows/path_sap_discovery.json` — success (statelessness guard), graceful `SAP_ERROR`, hard agent-failure, modeled directly on `path_sap_inquiry_execution.json`. `subworkflows/path_agent_intent_finder.json` has a `discover` case mirrored on its existing `match` case. `path_backbone.json` has a case proving the Router's new rule dispatches to `SAP: Discovery`, mirrored on the (dead-in-production) `sap_inquiry_execution` case.
- **Live E2E**: `workflow/tests/integration/sap_discovery_e2e_test.py`, modeled on `resolve_lookup_e2e_test.py`. Confirmed live: a real cross-entity question (vendors supplying items in a named `ItemGroups` group) reaches `SAP: Discovery`, `Agent: Discover` makes a `GitHub MCP` index fetch + a `SAP MCP` `ItemGroups` lookup, and correctly stops on a genuine name collision instead of guessing. `sap_entity_create` never appears in the call sequence (a hard assertion, not just diagnostic, given this agent's autonomy).
