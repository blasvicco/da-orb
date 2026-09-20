# UC-6: Click a node in the Intention Graph sidebar to resume it

User clicks a paused node in the sidebar to reactivate it. Resolved entirely in Django — no webhook call, no n8n execution; n8n only sees the already-resolved `active_node_id`/`intention_nodes` on the next real message, reactivating the same node rather than starting a fresh one.

## Scenario

```
User loads a previous chat session, or is mid-session where a previous process was interrupted
(see UC-4): a paused "Create Purchase Request" node exists alongside the currently-active node.

User opens the Intention Graph sidebar and clicks "Create Purchase Request", then confirms.
```

**This entire mechanism is Django-only.** Clicking a node never involves n8n at all — no webhook call, no execution, nothing. n8n only ever receives whatever `active_node_id`/`intention_nodes` already is by the time the *next real message* fires, fully pre-resolved.

## Preconditions

At least two nodes exist in `intention_nodes`, one of them not currently active. Completing (or abandoning) an interrupting node now auto-resumes its own immediate parent (see UC-4) — so this click path matters for reaching a node the auto-resume walk *wouldn't* land on by itself: the interrupting node hasn't finished yet, or the target is a different paused branch entirely (not on the currently-active node's own ancestor chain), or the session was just reloaded and the user wants to jump straight to an older paused thread. This doc's own scenario needs the interrupting process still mid-flight — e.g. the state right after UC-4's park step (turn 3, right after node registration, before List Vendors itself completes): `active_node_id: "2#1"`, `intention_nodes: {"1#0": {status: "paused", form_state: {RequriedDate: "2026-09-01"}}, "2#1": {status: "active", parent_id: "1#0"}}`. If List Vendors had already completed by the time of the click, auto-resume would already have reactivated `"1#0"` on its own — there'd be nothing left to click for that specific case.

## Step-by-step trace

### Frontend

1. `app/frontend/src/components/intention/stack.vue` — clicking a node's label only does something if it's not already active:
   ```js
   const onLabelClick = (node) => {
     if (node.status === 'active') return;
     openOverlay.value = { id: node.id, kind: 'navigate' };
   };
   ```
   This opens an `a-popconfirm` (`chat.intentionGraph.navigateConfirm`: *"Load the '{label}' intent context?"*) — **not immediate**, requires an explicit yes.
2. Confirming fires:
   ```js
   const onConfirmNavigate = (node) => { openOverlay.value = null; handleNavigate(node); };
   const handleNavigate = (node) => { emit('update:open', false); emit('navigate', { id: node.id, label: node.label }); };
   ```
   This closes the drawer and bubbles a `navigate` event up through `AttachMenu`/`ChatInput` to `chat.vue`.
3. `app/frontend/src/views/chat.vue`'s `handleNavigate`:
   ```js
   const handleNavigate = ({ id, label }) => {
     chat.switchActiveNode(id);
     messages.value.push({ text: t('chat.intentionGraph.contextSwitch', { label }), time: _timestamp(), type: 'system' });
     scrollToBottom();
   };
   ```
   Two things happen, both immediately, neither waiting for a server response:
   - `chat.switchActiveNode(id)` (`app/frontend/src/modules/websocket/chat.js`) sends `{ active_node_id: id, type: 'active_node.switch' }` over the already-open WebSocket.
   - A local `type: 'system'` bubble is pushed client-side (*"Context switched — now in **Create Purchase Request**."*) — pure UI feedback, not a round trip.

### Backend

4. `web_socket/consumers/chat.py`'s `receive_json` dispatches `type: 'active_node.switch'` → `active_node_switch(content)`:
   ```python
   target_id = content.get("active_node_id")          # "1#0"
   current = await self.n8n_state.load()               # {active_node_id: "2#1", intention_nodes: {...}}
   nodes = current.get("intention_nodes") or {}
   target = nodes.get(target_id)                        # the "1#0" node — exists
   if not target or target_id == current.get("active_node_id"):
       return                                            # unknown id or already active -- no-op
   updated_nodes = dict(nodes)
   old_active_id = current.get("active_node_id")         # "2#1"
   if old_active_id and old_active_id in updated_nodes and updated_nodes[old_active_id].get("status") == "active":
       # Only an actually-active node gets parked — a completed/failed node
       # active_node_id happens to still point at must not be relabeled "paused",
       # same guard Park Current Intent (n8n side) already applies.
       updated_nodes[old_active_id] = {**updated_nodes[old_active_id], "status": "paused"}
   # A genuinely resumable node (failed/paused) gets reactivated to "active"; a
   # completed/abandoned node's own status is left untouched — active_node_id still
   # moves to it so context questions can reference it, but clicking a finished node
   # never resurrects it as if it were still pending.
   target_status = target.get("status")
   new_target_status = "active" if target_status in ("failed", "paused") else target_status
   updated_nodes[target_id] = {**target, "status": new_target_status}
   await self.n8n_state.save(active_node_id=target_id, intention_nodes=updated_nodes, last_bot_message=current.get("last_bot_message"))
   ```
5. Nothing else happens. No WS reply is sent back for this message type (fire-and-forget) — the frontend's own local system bubble is the only feedback the user sees, and it appeared before step 4 even ran.

**State immediately after the click (no new chat message sent yet):**
```json
{
  "active_node_id": "1#0",
  "intention_nodes": {
    "1#0": { "status": "active", "form_state": { "RequriedDate": "2026-09-01" } },
    "2#1": { "status": "paused", "parent_id": "1#0" }
  }
}
```
`"2#1"` was genuinely `active` before the click (still mid-form on List Vendors), so parking it to `paused` here is the expected, unremarkable case. `active_node_switch` guards this the same way `Intent Manager`'s `Park Current Intent` (n8n side) does — only a node still genuinely `active` gets relabeled `paused`; a `completed`/`abandoned` node `active_node_id` happens to still be pointing at (a brief window that now mostly closes itself via auto-resume, see UC-4) is left exactly as it is.

### The critical payoff — next real message sees pre-resolved state, n8n never involved in the switch

6. Whatever the user types next (e.g. "El proveedor es V10000") goes through `N8nClient.fire()`, which builds the outgoing webhook payload **from Redis, as it now stands** — `active_node_id: "1#0"`, `intention_nodes` with `"1#0"` already `active` again, `form_state.RequriedDate` still intact. There is **no `active_node_override` field anywhere in this payload** — n8n has no way to even know a switch happened, and doesn't need to.
7. `Agent: Find` sees an active, mid-form process (`"1#0"`, `RequriedDate` already filled) and the message plausibly continues it → `pending_reply` → `sap_form_filling` picks up exactly where it left off, with the previously-collected data intact — this is the entire point of the mechanism: **the same node is reactivated, not a fresh one**. Auto-resume (UC-4) already handles the common case — a paused node's own interrupting child finishing hands control straight back to it. This click path remains the way back to a paused node that auto-resume *wouldn't* reach on its own (a different branch entirely, or one whose interrupting child hasn't finished yet) — short of a message `Agent: Find` happens to classify as continuing it directly.

## Spec test outline

Closest existing model: `workflow/tests/integration/active_node_switch_django_direct_test.py` (already covers exactly this mechanism end-to-end) — model any new case on it directly rather than writing from scratch.

- **Django unit test** (`app/backend/web_socket/tests/consumers/chat_test.py`): the "# active_node_switch" section already has 5 tests covering unknown-id no-op, already-active no-op, park+activate, etc. Add one for the "clicking away from a *completed* node still marks it paused" nuance above if it isn't already covered — check the existing 5 cases before assuming it's missing.
- **Live E2E, Django-direct (no WS, no n8n)**: exactly `active_node_switch_django_direct_test.py`'s pattern — construct a bare `CChat()` instance, set `.n8n_state` directly, call `.active_node_switch({...})`, assert via `N8nSessionState.load()`. This is the fastest, cheapest way to verify the mechanism itself, since it needs neither a live WebSocket connection nor an n8n execution.
- **Live E2E, full stack**: start a PR, interrupt it (UC-4), then send the real `active_node.switch` WS message (or, if testing through the actual frontend, drive a browser via `chrome-devtools` MCP per this repo's `CLAUDE.md` setup) and confirm a *subsequent* real n8n turn correctly treats the reactivated node as `pending_reply` with its old `form_state` intact and zero `active_node_override` anywhere in the raw webhook payload n8n receives (inspect via `client.get_node_output(execution, 'Webhook')`, same technique as `active_node_switch_django_direct_test.py`).
- **Regression guard**: assert clicking an **already-active** node is a true no-op (`Already the active node` early-return path) — confirm no local system bubble side effect issue either, since the frontend's `onLabelClick` already guards this (`if (node.status === 'active') return`) before the WS message is ever sent.
