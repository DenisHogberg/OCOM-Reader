"""Reader's implementation of docs/contracts/companion-reader-contract.md — the
versioned API boundary published by the Companion repository (Contract Version 1.1,
grounded in Companion's PARSER_VERSION 1.4.0 and its M07 multi-transcript
validation). See companion_integration/models.py for the field-level contract and
companion_integration/signals.py for why detected_signals is queried per-signal,
never by combination.

This package only reads Companion's Markdown+YAML-frontmatter objects. It never
writes back into a Companion repository — Reader has no role in Companion's own
write-back governance (Companion's docs/ai-collaboration.md).
"""
