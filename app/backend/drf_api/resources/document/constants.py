"""Shared constants for the document and document_template resources"""

# The fixed set of document types Phase 1 recognizes, and the bundled system-fallback
# template file for each — used both to validate an incoming document_type and, when an org
# has no default MDocumentTemplate of its own, as the render fallback (see
# docs/plans/document_generation_and_templates.md's resolved "always fallback" open question).
SUPPORTED_DOCUMENT_TYPES = {"invoice": "invoice_default.rpt"}
