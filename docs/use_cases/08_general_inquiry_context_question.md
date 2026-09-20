# UC-8: General inquiry / context question mid-flow

Mid-flow, the user asks a side question instead of answering the form (why a field's needed, what a file said, what's happened so far, what went wrong). All four are answered by the same node path, drawing on different slices of the current context; nothing about the active process changes.

## Scenario

```
Mid-form-fill (node "1#0" active, some fields already collected), user asks a side question
instead of answering:
"¿Por qué necesitas esa fecha?"       (why do you need that field)
"¿Qué decía el archivo que subí?"     (what was in that file — see UC-12)
"¿Qué hemos estado haciendo?"         (what have we been doing)
"¿Qué salió mal?"                     (what went wrong — after a prior error, see UC-11)
```

All four are answered by the same node path; they only differ in which slice of the context block the answer actually draws from.

## Preconditions

At least one node in `intention_nodes` with something worth asking about — an active node with partial `form_state` for the first example, `extracted_files` present from a recent turn for the second, any nodes at all for the third, a node whose `intention_nodes[id].status === 'failed'` for the fourth.

## Turn-by-turn trace

**`agent-intent-finder.json`:**
- `Agent: Intention Focus` sees the message doesn't progress or abandon the open item — it's a meta-question about it. `Agent: Find` classifies `{"status": "general_inquiry"}` — per its own systemMessage, this is a genuine question "that has NOTHING to do with the current pending item" *in the sense of not answering/progressing it*, while still being allowed to reference it for context (the general-inquiry prompt explicitly expects this: *"'why do you keep asking for X' can reference active_process"*).
- `Compute Route Key`: `general_inquiry` → **`route_key = 'general_inquiry'`**.

**`intent-manager.json`:** `Needs Park Before New?` false (`status !== 'new_intent'`) — the open node is **not** touched, parked, or otherwise affected. General inquiry is a pure side-channel.

**`context-update.json`:** `Needs Resolution?` false (`processes` is absent on a `general_inquiry` turn) → straight through, no schema fetch, no node registration.

**`Router` → `General Inquiry` → `general-inquiry.json`:**
1. `Status Text: Answering` / `Status: Answering` broadcast `"Respondiendo..."`.
2. `Prompt: Context & Conversation` builds a `contextBlock` from the **current, live** state (not anything round-tripped from a prior turn):
   ```js
   const activeNode = nodes[data.active_node_id] || null;
   const lastFailedNode = [...nodeList].reverse().find((n) => n.status === 'failed') || null;
   const contextBlock = {
     active_process: activeNode ? { process_id: activeNode.process_id, name: activeNode.process_definition?.name, collected_so_far: activeNode.form_state } : null,
     last_error: error ? { code: error, detail: lastFailedNode?.error_detail || activeNode?.error_detail || null } : null,
     attached_files: (extracted_files || []).map((f) => ({ bucket_file_id: f.bucket_file_id, content_preview: (f.extracted_content || '').slice(0, 2000), error: f.error })),
     recent_intention_nodes: nodeList.slice(-5).map((n) => ({ id: n.id, process_id: n.process_id, status: n.status })),
   };
   ```
   **Important:** `last_error` here is computed **fresh, this turn**, from the current turn's own `error` field and a live scan of `intention_nodes` for a `failed` node — it is *not* reading any persisted "last error" from a prior turn; no such field exists in the persisted state (see the README's state-shape section). So this only works if the current turn's `error` happens to be set (i.e. asking "what went wrong" works right after an error, riding the same turn) or if a node is still sitting there `status: 'failed'` from a previous turn (its `error_detail`, if present, still gets picked up by `lastFailedNode`).
3. `Agent: Context & Conversation`: answers using whichever slice of `contextBlock` is relevant, in the user's language, refusing to fabricate values not present in the block, and explicitly refusing to trigger/confirm/execute any SAP action itself even if asked.
4. `Agent: Context & Conversation`'s output → `Merge Context: Context & Conversation` (a `Set` node re-merging `Prompt: Context & Conversation`'s own pre-call context — an Agent node's output otherwise replaces the item entirely) → `Execute Workflow: Error Parser` (the shared `error-parser.json`, called unconditionally right after the agent — see the README's error-gate note and UC-11) → `Was Handled?` false → `Lift Message` (extracts `message` from the gate's own parsed `_parsed.message`, falling back to the raw `output` text if parsing failed — this file has no further routing step of its own, so it's the only caller that needs this extra one-line adapter) → `Execute Workflow: Response` → Django callback. `state.intention_nodes`/`active_node_id` are **unchanged** — general inquiry never writes state, only reads it.

**Final state:** identical to before the turn. Delivered message: `type: "agent"`, a conversational answer.

## A real, documented gap: "why do you need that field" can't actually cite the field's own description

`Prompt: Context & Conversation`'s `active_process` block only carries `{process_id, name, collected_so_far}` — `collected_so_far` is `activeNode.form_state`, i.e. only the **values already filled in**. It does **not** include `process_definition.form.sections[].fields[].ask`/`.description` — the actual authored text that explains *why* a field exists or what it's for. So when a user asks "why do you need the required date," the agent has no authoritative source for the answer beyond its own general SAP knowledge; it cannot correctly quote the schema's own `ask` text (e.g. *"What is the date by which the goods are required?"*) because that text was never handed to it. The prompt's own intro sentence implies this should work (*"'why do you keep asking for X' can reference active_process"*) but the actual data contract underneath doesn't fully support it. Flagged here so a spec test doesn't assert the agent can correctly recite field-level schema text, since the data to do so correctly isn't in its context.

## A second, related gap: `last_error` is undocumented in the agent's own prompt

`Agent: Context & Conversation`'s systemMessage gives worked examples for `active_process`/`attached_files`/`recent_intention_nodes` but never mentions `last_error` exists or how to use it — despite it being a real, tested part of the input contract (see `workflow/tests/cases/unit/prompt_context_conversation.json`'s "what went wrong?" fixture). See UC-11 for the fuller error-handling trace this connects to.

## Spec test outline

Closest existing model: `workflow/tests/cases/unit/prompt_context_conversation.json` (Tier 1, already covers all four `contextBlock` fields individually) and `workflow/tests/cases/integration/subworkflows/path_general_inquiry.json` for the Tier 2 level.

- **Tier 1**: the existing `prompt_context_conversation.json` cases are the right level for verifying `contextBlock`'s shape — extend rather than duplicate if a new field/scenario needs covering.
- **Tier 2**: pin `Agent: Context & Conversation`'s output, assert `Execute Workflow: Response`'s final `state` object is byte-for-byte identical to the input `intention_nodes`/`active_node_id` (the "general inquiry never mutates state" invariant) — this is the one thing worth a dedicated regression case, since it's easy to accidentally break by adding a well-intentioned "helpful" side effect to this file later.
- **Live E2E**: start a form-fill, ask "why do you need that field" mid-way, assert (a) the delivered reply doesn't hallucinate a field name/value not in `collected_so_far`, (b) a **follow-up** turn supplying the actual field value still works normally (proving the side question truly didn't disturb the open node's state) — model on the multi-turn structure of `workflow/tests/integration/intention_node_form_state_sync_test.py`.
