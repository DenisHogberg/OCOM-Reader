# ADR-001: Normalizer as a Separate, Replaceable Layer

**Status:** Accepted
**Date:** 2026-07-22
**Applies to:** `ocom_reader.interfaces.normalizer.Normalizer` and its implementations

## Decision

`Normalizer` is a distinct architectural layer, separate from `Adapter`,
the Core Object Model (`OCOMObject`, `Evidence`), and `Storage`. Each
lives in its own package (`adapters/`, `normalizers/`, `core/`,
`storage/`) and is connected to the others only through the interfaces
in `interfaces/`.

Concretely:

- **Separate from Adapter.** `Adapter.fetch()` returns raw,
  source-shaped records (e.g. `RawDocument`) and knows nothing about
  `OCOMObject`. `Normalizer.normalize(raw) -> OCOMObject` is the only
  place raw data is turned into the OCOM model. An Adapter never
  constructs an `OCOMObject`; a Normalizer never touches a filesystem,
  API, or database directly.
- **Separate from the Core Object Model.** `OCOMObject` and `Evidence`
  do not know that Normalizers exist. They are plain data models
  (pydantic) with no dependency on `interfaces/` or any concrete
  Normalizer. A Normalizer depends on the core; the core does not
  depend on any Normalizer.
- **Separate from Storage.** `Storage` persists and retrieves
  `OCOMObject` instances and has no knowledge of how they were
  produced. A Normalizer never calls `Storage` directly — that
  connection is made by whatever code drives the pipeline (currently
  test code and `main.py`, not the Normalizer itself).

Two implementations exist today and both satisfy the same contract:
`FilesystemDocumentationNormalizer` (deterministic, no LLM) and
`LLMDocumentNormalizer` (LLM structured output, injected `LLMClient`).
Neither implementation required a change to `Adapter`, `Storage`,
`OCOMObject`, or `Evidence` to exist.

## Context

Three problems motivate keeping this boundary strict:

1. **Different sources produce different raw shapes.** A filesystem
   document, a GitHub issue, a CRM record, and a payment event have
   nothing in common at the raw level. If normalization logic lived
   inside the Adapter (or the Adapter returned `OCOMObject` directly),
   every new source would need to re-implement identity, metadata, and
   evidence construction independently, with no shared contract and no
   guarantee of consistency (violates Core/Modeling-Rules.md.docx Rule
   8 — "Models must avoid duplication").
2. **Different sources require different extraction strategies.**
   Extracting meaning from a well-structured CRM record is not the
   same problem as extracting meaning from free-text documentation.
   Some extraction is deterministic (file metadata), some requires
   interpretation (LLM structured output), and some may later require
   other techniques entirely (rule engines, classic NLP, human review).
   None of that variation should be visible to `Adapter`, `Storage`, or
   the Core Object Model.
3. **The AI model behind extraction must be replaceable without
   touching the core.** `LLMDocumentNormalizer` depends on an injected
   `LLMClient`, not a hardcoded vendor SDK call. Swapping models,
   providers, or even removing the LLM entirely (as
   `FilesystemDocumentationNormalizer` proves) is a Normalizer-level
   change only. `OCOMObject`, `Evidence`, `Adapter`, and `Storage` are
   proof, by construction, that this is possible: neither has changed
   since the deterministic Normalizer was introduced.

## Current Implementation

```
Source
 ↓
Adapter
 ↓
Raw Data
 ↓
Normalizer
 ↓
OCOM Object
 ↓
Evidence
 ↓
Storage
```

Notes on how this maps to the code:

- `Evidence` is not a separate pipeline stage after `OCOM Object` — it
  is constructed by the Normalizer as part of building the `OCOMObject`
  (`OCOMObject.evidence: list[Evidence]`). The diagram is accurate as a
  statement of dependency order (an `OCOMObject` without `Evidence` is
  incomplete for this pipeline's purposes), not as a statement that
  Evidence is produced by a separate component.
- Today's concrete pipeline:
  `FilesystemDocumentationAdapter` → `RawDocument` →
  (`FilesystemDocumentationNormalizer` | `LLMDocumentNormalizer`) →
  `OCOMObject` (with `Evidence` attached) → `LocalJSONStorage`.
- Nothing outside `normalizers/` changed between the deterministic and
  LLM-based Normalizer. That is the concrete evidence this decision is
  working, not just an intention.

## Future Direction

New sources and new storage backends are expected to be added as new
implementations of the existing interfaces, not as changes to them:

- **GitHub Adapter** — a new `Adapter` + a new `Normalizer` (raw GitHub
  API shapes differ completely from `RawDocument`; a new Normalizer is
  expected, possibly reusing an LLM-based extraction pattern).
- **CRM Adapter** — same pattern: new `Adapter`, new `Normalizer`.
- **BI Adapter** — same pattern.
- **Knowledge Graph Storage** — a new `Storage` implementation
  (`interfaces/storage.py` unchanged); Normalizers do not need to know
  which `Storage` implementation is in use.
- **Advanced Evidence Overlay** (confidence scoring, verification
  workflow, write-back governance per Memory/Evidence Overlay.md.docx
  and Memory/Confidence.md.docx) — expected to extend how Normalizers
  populate `Evidence`/`metadata`, not to change the `Evidence` or
  `OCOMObject` schema, unless a real use case proves the current shape
  insufficient. If that happens, it should be its own ADR.

If implementing any of the above turns out to require a change to
`Adapter`, `Normalizer`, `Storage`, `OCOMObject`, or `Evidence`, that is
a signal to stop and re-examine this decision rather than force the
change through — the whole point of this boundary is that it shouldn't
be necessary.
