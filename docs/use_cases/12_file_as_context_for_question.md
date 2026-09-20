# UC-12: Attach a file as context for a question (not for record creation)

User attaches a file purely as context for a question, not for record creation. Shares UC-3's file-extraction pipeline; the two diverge only at `Agent: Find`'s classification.

## Scenario

```
User attaches a PDF (e.g. a supplier quote) and asks:
"¿Qué dice este documento?"
(= "What does this document say?")
```

Shares the exact same file-extraction pipeline as **UC-3** (file upload → batch creation) — the divergence happens entirely at `Agent: Find`'s classification. This doc only traces what's different.

## Preconditions

The file already exists in the session's bucket, `bucket_file_ids: [103]`.

## Turn-by-turn trace

### File extraction (identical mechanism to UC-3)

`context-enrichment.json` → `file-extraction-core.json` → (cache check → download → mime-route → extract → normalize → persist, per file) → `extracted_files: [{bucket_file_id: 103, extracted_content: "<full PDF text>", error: null}]`.

### Turn 1 — the question

**`agent-intent-finder.json`:**
- `Agent: Find`: the message is a genuine question, not an actionable SAP request and not a reply to anything pending → `{"status": "general_inquiry"}`. Note: even though the message references an attached file, this does **not** trigger the batch-classification rule ("if the request references attached files, use whatever file content already appears in the INPUT JSON to identify the process(es)") — that rule only applies once the agent has already decided the message is a `new_intent` asking to create/submit something. Asking "what does this say" is never a create/submit request, so it never reaches that branch at all.
- `Compute Route Key` → **`route_key = 'general_inquiry'`**.

**`intent-manager.json` / `context-update.json`:** no park, `Needs Resolution?` false — both pass `extracted_files` through untouched (neither file manipulates it).

**`Router` → `General Inquiry` → `general-inquiry.json`:**
- `Prompt: Context & Conversation`:
  ```js
  attached_files: (extracted_files || []).map((f) => ({
    bucket_file_id: f.bucket_file_id,
    content_preview: (f.extracted_content || '').slice(0, 2000),
    error: f.error,
  }))
  ```
  **This is the only place in the entire system that caps file content** — 2000 characters. Contrast with UC-3's batch path, which embeds the full, uncapped `extracted_content` into `Agent: Extract Batch Records`'s prompt (see UC-2). A long PDF's tail is silently unavailable to this Q&A path even though it was fully extracted and would have been fully available for record creation.
- `Agent: Context & Conversation`: answers using `attached_files`, per its own rule *"do not fabricate content not present there"* — if the question asks about something past the 2000-character mark, the agent has no way to answer it correctly and (per its own fallback rule) should say the information isn't available rather than guess.
- If extraction failed for this file (`error: "UNSUPPORTED_MIME_TYPE"`, e.g. the user attached a `.docx` or a screenshot image), `content_preview` is empty and `error` is set — the agent should recognize it can't read the file rather than pretend it can.

**Final state:** unchanged — general inquiry never writes state, same as UC-8.

## Spec test outline

Closest existing models: `workflow/tests/cases/unit/prompt_context_conversation.json` (already has an `attached_files` case, including a case with `error` set on the extracted file — check before duplicating) combined with UC-3's file-extraction Tier 2 test once it exists.

- **Tier 1**: extend `prompt_context_conversation.json` with a case whose `extracted_content` exceeds 2000 characters, asserting `content_preview` is truncated to exactly 2000 — this is the one behavior genuinely specific to this use case versus UC-3's uncapped batch path, and it's easy to accidentally regress if someone "fixes" the cap without realizing the batch path deliberately has none.
- **Tier 2**: a case chaining `path_file_extraction_core.json` (once it exists, per UC-3's outline) into `path_general_inquiry.json`, asserting the final `attached_files` block both truncates correctly and carries the `error` field through when extraction failed.
- **Live E2E**: attach a real file with known, distinctive content near/past the 2000-char mark, ask a question whose answer lives past that mark, and confirm the agent correctly says it can't find that information rather than fabricating an answer — this is the one thing that can't be verified by inspecting node output alone, since it depends on the LLM actually respecting its own no-fabrication rule under a real truncation.
