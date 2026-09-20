# UC-7: Load a previous chat session

User reopens a past session with an in-progress process in its graph. Redis state and the message transcript are restored independently over WebSocket and REST; the sidebar renders the full historical tree once both arrive.

## Scenario

```
User opens the app, sees a list of past chats in the sidebar, and clicks one that has an
in-progress purchase request (a paused or active node) in its Intention Graph.
```

## Preconditions

A `MChatSession` row exists with a non-null `n8n_state` column (Django persists this on every callback — see `n8n_callback` in `app/backend/drf_api/resources/chat/main.py`: `MChatSession.objects.filter(pk=session.pk).update(n8n_state=effective_state)`), e.g.:
```json
{ "active_node_id": "1#0", "intention_nodes": { "1#0": { "status": "active", "form_state": { "RequriedDate": "2026-09-01" } } }, "last_bot_message": "..." }
```

## Step-by-step trace

### Frontend

1. Sidebar list (`sessions.value`, from `AppAPI.Chat.sessions()`, `GET /api/v1/chat/sessions/`) already carries each session's `n8n_state` — this is what's populated on WS `open` and refreshed after various message events, independent of this flow.
2. User clicks a `SessionItem` → bubbles up through `ChatHistory` → `chat.vue`'s `loadSession(id)`:
   ```js
   const loadSession = async (id) => {
     messages.value = [];
     isTyping.value = !!sessions.value.find((s) => s.id === id)?.pending;
     pendingContextFiles.value = [];
     sessionId.value = id;
     statusText.value = null;
     chat.sessionId = id;
     chat.disconnect();
     setTimeout(() => chat.connect(), 300);

     const result = await AppAPI.Chat.messages(id);
     if (!result?.errors) {
       messages.value = result.map((m) => ({ ... }));
       scrollToBottom();
     }
   };
   ```
   **Exact order:** local state reset → `chat.sessionId = id` (the resume-id field on the WS wrapper) → WS `disconnect()` → WS `connect()` scheduled 300ms later → `GET /api/v1/chat/messages/?session_id={id}` fired **in parallel**, not awaited before the reconnect kicks off.

### WebSocket reconnect / state restore

3. `Abstract.connect()` opens a new `WebSocket`; on `onopen` it calls `_sendAuthInit()`:
   ```js
   { type: 'auth.init', password, database, session_id: this.sessionId }
   ```
   `session_id` is present because step 2 set `chat.sessionId = id`.
4. Backend `CChat.auth_init` → `resolve_context()`:
   ```python
   if self._resume_session_id:
       self.chat_session = await _load_session(connection_key=..., org_id=..., session_id=self._resume_session_id, username=...)
       if self.chat_session and self.chat_session.n8n_state:
           await self.n8n_state.restore(self.chat_session.n8n_state)
   ```
   `N8nSessionState.restore()` writes the persisted dict to Redis **as-is** (`await self._redis.set(self._key, json.dumps(state), ex=self._ttl)`) — this bypasses `save()`'s field whitelist entirely, so whatever was persisted (which, by construction, is only ever `active_node_id`/`intention_nodes`/`last_bot_message`, since that's all `save()` ever wrote in the first place) comes back intact.
5. Server replies `auth.ok`; frontend's `chat.on('auth', ...)` re-syncs `sessionId.value`/`chat.sessionId` from the response (belt-and-suspenders in case it differs — relevant on a page refresh rather than a sidebar click, where the frontend doesn't know the id ahead of time and this is the only way it finds out).
6. WS `open` handler calls `refreshSessions()` (`GET /sessions/` again), refreshing the sidebar list — including each session's own `n8n_state` — which feeds `currentSessionState`.

### Rendering the Intention Graph from the reloaded state

7. `currentSessionState` (a computed in `chat.vue`) is passed down `ChatInput` → `AttachMenu` → `IntentionStack` as `sessionState`.
8. `app/frontend/src/modules/chat/intention/stack.js`'s `deriveIntentionNodes(messages, fallbackState)`:
   ```js
   const latestState = (messages) => {
     for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
       if (messages[idx]?.state) return messages[idx].state;
     }
     return null;
   };
   export const deriveIntentionNodes = (messages, fallbackState) => {
     const state = latestState(messages || []) || fallbackState || null;
     if (!state) return [];
     const nodes = Object.values(state.intention_nodes || {});
     return nodes.map((node) => ({ id: node.id, label: labelFor(...), parentId: node.parent_id, status: node.status, errorDetail: node.error_detail ?? null }));
   };
   ```
   This is exactly why `fallbackState` (the reloaded session's persisted `n8n_state`) matters: messages loaded via the REST history endpoint carry **no** per-message `state` field (only live WebSocket delivery messages do) — without the fallback, the sidebar would render empty until the user's next real turn.
9. `buildIntentionTree(nodes)` nests the flat list by `parent_id` into the `{key, title, children}` shape the tree component renders. **Confirmed: this renders the entire flat set of every node ever created in that session — not filtered to the current active node's ancestry.** A node whose parent isn't in the set becomes its own root. So a session with several old, unrelated, fully completed/failed/parked processes shows all of them as separate branches in the sidebar, side by side with whatever is active now.

## Final state

Redis now mirrors exactly what was last persisted for this session; the sidebar renders the complete historical tree; the message transcript (from the REST call) and the live state (from the WS restore) arrive independently and don't have to race correctly against each other for the UI to end up correct, since the sidebar always has a valid fallback.

## Spec test outline

No dedicated live E2E script for this exists yet in `workflow/tests/integration/` (n8n-focused tests in this repo assume a session already exists) — this is a **Django + frontend** concern, not an n8n one.

- **Django unit test**: `app/backend/web_socket/tests/consumers/chat_test.py` should already have coverage for `resolve_context()`'s restore branch (`self.n8n_state.restore(self.chat_session.n8n_state)`) — verify it asserts the exact dict passed to `restore`, not just that it was called.
- **Django unit test**: `N8nSessionState.restore()` itself (`app/backend/web_socket/tests/helpers/n8n/state_test.py`) — confirm a round-trip (`restore(x)` then `load()`) returns exactly `x`, including a case where `x` has extra/legacy keys (proving `restore` really does bypass `save()`'s whitelist, for better or worse — this matters if a session persisted before a state-shape migration needs to still load without crashing).
- **Frontend unit test** (`app/frontend/src/tests/modules/chat/intention/stack.test.js`): a case for `deriveIntentionNodes` using **only** `fallbackState` (empty `messages` array) — proving the reload path specifically, not just the live-message path most other tests there likely cover.
- **Frontend unit test**: a case with multiple *unrelated* root nodes (no shared ancestry) proving the "renders the full flat history, not just the active node's chain" behavior — this is easy to get wrong in a future refactor that "helpfully" tries to prune the tree to just what's relevant right now.
- **Live E2E** (new): create a session, drive 2 real turns to get a real `n8n_state` persisted (via the normal webhook path), then simulate a reload by constructing a fresh WS `auth_init{session_id}` directly (bypassing the browser) and asserting the restored Redis state matches what was persisted — closest existing pattern to build from is `active_node_switch_django_direct_test.py`'s use of `manage.py shell` to invoke Django code directly, adapted to call `resolve_context()`'s restore path instead of `active_node_switch`.
