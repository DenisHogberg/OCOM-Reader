"""Reader's implementation of docs/contracts/vector-reader-contract.md — the
versioned API boundary published by the Vector repository (Contract Version 1.1,
grounded in Vector's PARSER_VERSION 1.4.0 and its M07 multi-transcript
validation). See vector_integration/models.py for the field-level contract and
vector_integration/signals.py for why detected_signals is queried per-signal,
never by combination.

This package only reads Vector's Markdown+YAML-frontmatter objects. It never
writes back into a Vector repository — Reader has no role in Vector's own
write-back governance (Vector's docs/ai-collaboration.md).
"""
