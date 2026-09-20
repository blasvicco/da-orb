# UC-14: Generate a document (PDF) of a completed process

Status: **Phase 1 only** — see `docs/plans/document_generation_and_templates.md` §8. One
hard-coded system template (a placeholder fixture standing in for a real invoice `.rpt` — see
"Notable gaps"), no `DocumentTemplate` model, no admin authoring, no BP/language overrides.

## Scenario

```
User just created a purchase request (or any completed SAP process) earlier in the same
session, then says: "genera un PDF de eso" / "mandame la factura en PDF".
```

## Preconditions

At least one entry in `intention_nodes` with `status: "completed"` (or `"active"`) whose
`form_state` the user is asking to be rendered as a document.

## Turn-by-turn trace

**`agent-intent-finder.json`:**
- `Prompt: Intention Focus` / `Agent: Intention Focus` run as on every turn, unchanged —
  their `focus` statement is available as grounding context but this use case doesn't depend
  on it beyond what STEP 0 already covers for every classification.
- `Agent: Find` — new STEP 1 branch: recognizes a document/file/PDF export request as
  `status: "generate_document"`, distinct from both `new_intent` (never a new SAP action) and
  `general_inquiry` (a question about the document/process, not a request to receive the file
  itself, still routes to `general_inquiry`). STEP 2 has it pick `target_node_id` from the raw
  `intention_nodes` object already in its own `INPUT JSON` (not the summarized INTENTION
  TREE) — the most recently active/completed node matching what the user named, or the most
  recent one if unspecified — and set `force_new_version: true` only when the message
  explicitly asks for a fresh/updated version.
- `Compute Route Key`: new branch, `content.status === 'generate_document'` →
  `route_key = 'generate_document'`. `target_node_id`/`force_new_version` ride through
  unchanged (spread from `content`, not explicitly handled — same as every other pass-through
  field on this node).

**`intent-manager.json`:** no park — `Needs Park Before New?` only fires for
`status === 'new_intent'`, so a `generate_document` turn never touches the currently active
node, same as `general_inquiry`.

**`context-update.json`:** `Needs Resolution?` is false (no `processes` array set for this
status) → straight through to `Return Context Update Result`, same as every non-form-filling
route.

**`Router`** → `Generate Document` (`route_key === 'generate_document'`, new switch output) →
`generate-document.json` (n8n workflow id `atVchF9qHwQRIZuM`):

1. `Resolve Target Node`: looks up `intention_nodes[target_node_id]` — reads the
   already-resolved id, never re-resolves which node the user means itself (same
   Router-dispatched-flows-assume-resolved-context convention every other route follows).
2. `Has Target?`: false → `No Target Found` (conversational "couldn't find which process you
   mean" message, `error: 'NOT_FOUND'`) → `Execute Workflow: Response`.
3. `Has Target?`: true → `Build Invoice Rows` — **placeholder mapping** (see "Notable gaps")
   from `form_state`'s `CardName`/`DocEntry`/`DocNum`/`DocTotal` into the bundled template's
   own declared short field names (`Product ID`, `Product Name`, `Color`, `Size`,
   `Price (SRP)`) — one flat row.
4. `Call Document Render`: `POST /api/v1/document/generate/` (`X-N8n-Secret` via the same
   "Orb Auth" credential every other Django callback node uses) with
   `{session_id, document_type: "invoice", data: [<row>], name: "factura_" + target_node_id, force_new_version}`.
5. `Handle Render Result`: `statusCode === 201` → success message + `attachment: {id, name}`.
   `statusCode === 409` → "a version already exists, ask me for a new one if you need it
   updated" message, same `attachment` (points at the existing file) so the chip still shows.
   Anything else → `error: 'RENDER_FAILED'` conversational message, no attachment.
6. `Execute Workflow: Response` → `response.json`'s `Build Callback Payload`: forwards
   `d.attachment` (when set) as `extra: { attachment: d.attachment }` — the general-purpose
   `extra` passthrough `n8n_callback` already spreads onto the broadcast payload, same
   mechanism `processes` uses (no new Django serializer field needed).

**Django (`drf_api/resources/document/main.py`, `VSDocument.generate`):**
`PDocumentWrite` (a thin `PN8nCallback` subclass — same shared-secret header, no new secret)
gates the endpoint. Validates `document_type` against the fixed Phase 1 map
(`{"invoice": "invoice_default.rpt"}`), looks up the session (`MChatSession.objects.get`, no
org/username scoping — same trust boundary as `n8n_callback`), checks for an existing
`workflow_generated` `MBucketFile` named exactly `f"{name}.pdf"`:
- found, no `force_new_version` → `409` with that file's `SBucketFile` data, nothing rendered.
- found + `force_new_version` → `name` gets a `_<YYYYMMDDHHMMSS>` suffix, proceeds.
- not found → proceeds as-is.

Then `FReport.get_instance(driver=settings.REPORT_RENDER_DRIVER).render(template_path, {"rows": rows})`
(the `rpt_rs` driver: writes `rows` to a temp JSON file, shells out to the `orb-report-render`
binary — `app/renderer`, a small Rust binary built from `rpt-rs`'s library crates, see the
plan doc's Step 1) → `FStorage.get_instance(driver=settings.STORAGE_DRIVER).upload(...)` into
the session's bucket, same `MBucketFile`/`build_storage_key()` convention the upload endpoint
already uses, `origin="workflow_generated"`.

**Frontend:** `msg.attachment` (spread through from `extra.attachment`, both the live WS path
in `chat.vue`'s `onAgentMessage` and the history-load path via `m.extra?.attachment`) renders
a `DocumentChip` inside the agent bubble — a small name + download button, calling the
existing `AppAPI.Bucket.downloadUrl(id)` → presigned URL → `window.open`, no new frontend API
method needed.

## Final state

No new `intention_nodes` entry, no change to `active_node_id` — this route only ever reads an
existing node, never creates or mutates one. A new `MBucketFile` row exists in the session's
bucket (`origin: "workflow_generated"`), visible in both the chat bubble's chip and the
existing bucket drawer.

## Notable gaps (see also plan doc §7/§8)

- **The bundled template is a placeholder, not a real invoice layout.** It's
  `tests/fixtures/reports/benbrahim777/Product Price List.rpt` from the `rpt-rs` project's own
  test corpus (an "Xtreme Mountain Bikes" Crystal Reports sample, MPL-2.0-adjacent per that
  project's fixture licensing notes), repurposed because it's a proven-working flat report —
  not because its fields mean anything invoice-shaped. `Build Invoice Rows`' field mapping
  (`CardName` → `Product Name`, `DocTotal` → `Price (SRP)`, etc.) is correspondingly
  contrived. Swapping in a real invoice `.rpt` only requires updating that one Code node's
  mapping and the bundled file at `core/templates/documents/invoice_default.rpt` — the
  renderer, endpoint, and n8n wiring are otherwise generic to whatever fields a template
  declares (see `app/renderer/src/main.rs`'s `field_key()` — it reads the target `.rpt`'s own
  declared database fields and matches JSON keys by short name, not a hardcoded schema).
- **[Resolved, was a self-inflicted false alarm] Grouped reports render correctly via
  `RenderSource::Rows` (custom injected data), *given field keys shaped the way
  `app/renderer`'s own mapper actually looks them up.* An earlier version of this doc claimed
  `Customer Orders, Grouped by Country.rpt` silently lost its group headers/detail rows under
  pushed data. Re-tested directly against the real `orb-report-render` binary with 3 rows
  across 2 countries, keyed by plain short field names (`"Customer Name"`, `"Country"`, etc.,
  matching `field_key()`'s short-name convention) — full success: group headers, detail rows,
  correct per-group subtotals, correct grand total. The original test that produced the false
  "broken" reading had fed qualified `"Table.Field"`-style keys, a shape `field_key()` never
  looks up by — an own test-data bug, not a rendering bug. Separately, a real (and genuinely
  unconditional, not grouping-specific) `rpt-rs` decode bug was found and root-caused in a
  parallel debugging session against the `blasvicco/rpt-rs` fork: `FieldDef.long_name` is
  always `None` for every database field, because the Contents-stream decoder reads but
  discards a `field_id` handle that should join against the QESession stream's `QeField`
  records to resolve it. That bug is real and worth fixing upstream (a PR is in progress), but
  turned out not to block `app/renderer` specifically — its `long_name.unwrap_or(field.name)`
  fallback already produces the exact "keyed by plain short name" shape proven to work above,
  independent of whether `long_name` itself is populated. **Net: no known rendering gap for
  grouped/repeating-line-item templates remains** — the earlier "don't assume flat-report
  success generalizes" caution is retracted.
- **The regenerate-vs-cache confirm loop is one-shot, not stateful.** A `409` produces a
  message inviting the user to ask for a new version; there's no pending-state tracking the
  way a form's `pending_reply` works — the user's follow-up just re-enters classification
  fresh, and `Agent: Find` has to infer `force_new_version` from that new message's own
  wording alone, with no memory of the specific 409 that prompted it beyond ordinary
  conversation history.
- **No use of the `PN8nCallback`-gated write endpoint's `force_new_version` retry loop is
  exercised anywhere except this one flow** — if a future document-generating flow is added,
  confirm it goes through the same `VSDocument.generate` endpoint rather than duplicating the
  version-check logic.

## Spec test outline

No existing test models this closely — it's new. Follow the conventions above.

- **Tier 1**: unit cases for `generate-document.json`'s Code nodes
  (`workflow/tests/cases/unit/`) — `Resolve Target Node` (found/not-found), `Build Invoice
  Rows` (field mapping from a representative `form_state`), `Handle Render Result`
  (201/409/failure branches). Also a case for `response.json`'s `Build Callback Payload`
  covering the new `attachment` passthrough, and `agent-intent-finder.json`'s `Compute Route
  Key` covering the new `generate_document` branch.
- **Tier 2**: new `path_generate_document.json` under
  `workflow/tests/cases/integration/subworkflows/`, pinning `Call Document Render`'s HTTP
  response and asserting `Handle Render Result`'s output shape, modeled on how other
  subworkflow cases pin an HTTP Request node's `fullResponse` output (see
  `schema-resolution.json`'s own Tier 2 case for the `{statusCode, body}` pin shape).
- **Not testable via pins**: `Agent: Find`'s new classification branch (recognizing "generate
  a PDF" phrasing and picking the right `target_node_id`) is real LLM judgment — needs a live,
  unpinned verification run (per this repo's own convention for prompt changes) against a real
  message like "genera un PDF de la factura que acabas de crear", not just static prompt
  review.
- **Live E2E**: complete a process in a session, then ask for its PDF; assert (a) a `201` (or,
  on retry, `409`) from `/api/v1/document/generate/`, (b) a new `workflow_generated`
  `MBucketFile` row, (c) the delivered chat message carries `attachment` and the frontend
  chip's presigned download actually resolves to a valid PDF.
