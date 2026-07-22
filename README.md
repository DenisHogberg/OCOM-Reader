# OCOM Reader

OCOM Reader is the first reference **Adapter** implementation of the OCOM
architecture — not a product, not a RAG, not a documentation chatbot. It
exists to prove out a clean, source-agnostic core that future Adapters
(GitHub, CRM, Jira, BI, payment systems, ...) can plug into without ever
touching it.

## Architectural principles (binding for this codebase)

- An `OCOMObject` is always source-agnostic. No source ever shapes its
  schema, and no adapter-specific detail leaks into its structure.
- Provenance is not incidental metadata. Where an object's data came
  from is a first-class architectural concept — `evidence` — kept
  structurally separate from `metadata`. `metadata` describes the
  object; `evidence` explains where its data came from.
- The Reader adapts to OCOM. OCOM never adapts to the Reader.
- Adding a new source must only ever mean adding a new `Adapter` +
  `Normalizer` pair — the core (`OCOMObject`, `Evidence`, interfaces,
  storage) does not change.

See [`Meta/Object.md.docx`](../Meta/Object.md.docx),
[`Core/Principles.md.docx`](../Core/Principles.md.docx),
[`Core/Modeling-Rules.md.docx`](../Core/Modeling-Rules.md.docx), and
[`Memory/Memory Record.md.docx`](../Memory/Memory%20Record.md.docx) /
[`Memory/Evidence Overlay.md.docx`](../Memory/Evidence%20Overlay.md.docx)
for the governing specification this model is derived from. `Evidence`
here is a minimal Phase 1 placeholder reserving the right place for
that future Evidence Overlay concept — not a full implementation of it.

## Structure

```
src/ocom_reader/
  core/
    object.py               OCOMObject + Relationship (pydantic models)
    evidence.py               Evidence (pydantic model)
  interfaces/
    adapter.py               Adapter — fetches raw records from one source
    normalizer.py             Normalizer — raw record -> OCOMObject (+ Evidence)
    storage.py                 Storage — persists/retrieves OCOMObject
  storage/local_storage.py  LocalJSONStorage — one JSON file per object
  config.py                 Settings (env-driven)
  logging_setup.py           Logging configuration
  main.py                     Entry point

  adapters/filesystem_documentation.py
    RawDocument                          — raw record (content, path, modified_at, metadata)
    FilesystemDocumentationAdapter        — walks a folder, yields RawDocument for .md/.txt

  normalizers/filesystem_documentation_normalizer.py
    FilesystemDocumentationNormalizer     — deterministic, non-LLM Normalizer v0.1
```

## Phase 1 scope

Project structure, `OCOMObject` working model, `Evidence`, the three
core interfaces, a local JSON `Storage`, config, logging, entry point.

## Phase 2 scope

The first concrete source: `FilesystemDocumentationAdapter`. It reads a
local folder, finds `.md`/`.txt` files, and returns only raw data —
content, path, timestamp, basic metadata (filename, extension, size).
It has no knowledge of `OCOMObject`, does not extract entities, does
not call an LLM, and does not normalize anything.

Nothing in `core/` or `interfaces/` changed to add this source — that
is the point of this phase.

## Phase 3 scope (current) — Normalizer v0.1, no LLM

`FilesystemDocumentationNormalizer` now has a real, fully deterministic
implementation of `normalize()`:

- **identity** — a stable id hashed from the resolved file path
  (`fsdoc:<sha256[:16]>`). It does not change when the file's content
  changes, only when its path changes.
- **object_type** — fixed at `"Document"`. No content interpretation.
- **metadata** — the raw record's technical metadata (filename,
  extension, size_bytes) plus `content_length`. Nothing about origin
  lives here.
- **evidence** — one `Evidence` entry per document: `source` names the
  adapter, `reference` is the file path, `captured_at` is the file's
  mtime, `excerpt` is the first 200 characters of content.

It deliberately does **not** attempt entity extraction, business
object recognition, or anything requiring interpretation of the
document's meaning — that needs an LLM (or an equivalent extraction
step) and stays out of scope until this LLM-free contract is proven.

This class only implements the existing `Normalizer` interface — a
future LLM-based Normalizer (structured output + JSON Schema
validation + confidence scoring) can replace it as a drop-in without
touching the interface, the Adapter, or the core.

[`tests/test_full_pipeline.py`](tests/test_full_pipeline.py) proves the
first complete pass: `Document -> Adapter -> Normalizer -> OCOMObject
-> Storage`.

## Phase 4 scope (current) — Reasoning Consistency Test v0.1

[`tests/test_reasoning_consistency_v0_1.py`](tests/test_reasoning_consistency_v0_1.py)
tests the OCOM Object idea itself, not LLM quality — no LLM is involved.
Two documents describe the same OCOM concept in different language and
wording, run through the existing pipeline. It documents three things:

1. The deterministic Normalizer assigns identity from file path, not
   content meaning, so the two documents get two different identities.
   Recognizing they describe the same real object requires
   interpreting content — that is reasoning, and this is the honest
   boundary of a non-LLM Normalizer, not a defect.
2. Each OCOMObject keeps its own Evidence — provenance from each
   source survives independently, before any merging.
3. The OCOMObject/Evidence shape does not block building a merged
   representation once something (a future LLM-based Normalizer, or a
   human) decides the two are the same object: it is just combining
   evidence lists under one identity, with no change to core.

This defines exactly what the next phase — an LLM-based Normalizer with
structured output — needs to supply: the decision that two sources
refer to the same object, nothing else.

## Running

```bash
pip install -e .
python -m ocom_reader.main
```

## Testing

```bash
pip install -e . pytest
pytest
```
