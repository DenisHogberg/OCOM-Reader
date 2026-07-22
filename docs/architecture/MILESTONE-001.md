# MILESTONE-001: OCOM Reader — Architecture Freeze v0.1

**Date:** 2026-07-22
**Status:** Frozen — this document marks the first architectural milestone before work begins on OCOM Agent v0.1.

## Goal of v0.1

Not a product, not a RAG, not a documentation chatbot. The goal of this
version was to build a minimal but *correctly shaped* architectural
core for OCOM: a source-agnostic Object model with first-class
provenance, behind interfaces that let a source and its extraction
strategy be replaced without touching the core. v0.1 set out to prove
that shape with the smallest possible real pipeline — one source
(local documentation), two Normalizer strategies (deterministic and
LLM-based) — rather than to cover many sources or produce polished
output.

## Hypotheses Tested

Each of these was a falsifiable architectural claim, checked by code
and a test, not just asserted in prose.

1. **"A source can be swapped without changing the core."**
   Tested by implementing two independent Normalizers
   (`FilesystemDocumentationNormalizer`, `LLMDocumentNormalizer`) and
   confirming, via `git diff`, that `core/object.py`, `core/evidence.py`,
   and every file in `interfaces/` were untouched by either addition.
   **Confirmed.**

2. **"Evidence can be a structurally separate concept from metadata
   without adding real complexity."**
   Tested by adding `Evidence` as its own model and an `OCOMObject.evidence`
   field, and round-tripping it through `LocalJSONStorage`.
   **Confirmed** — one field, one model, no cascading changes.

3. **"A deterministic, non-LLM Normalizer cannot recognize that two
   differently worded documents describe the same real-world object."**
   Tested by `tests/test_reasoning_consistency_v0_1.py`: two documents,
   same concept, different language, normalized independently.
   **Confirmed** — they produced two different identities, as expected.
   This is a proof of a boundary, not a defect: it is exactly the gap
   the next hypothesis was meant to close.

4. **"An LLM-based Normalizer can supply the missing semantic-identity
   decision without changing the core or any interface."**
   Tested by `tests/test_llm_normalizer_same_object_recognition.py`
   using an injected, deterministic fake `LLMClient`.
   **Confirmed for the injected-client scenario.** **Not yet tested
   against a real LLM API call** — no API key was available in this
   environment, so `AnthropicLLMClient` exists but has never actually
   been exercised. This is an open item, not a resolved one.

5. **"The OCOMObject/Evidence shape permits a merged, multi-source
   representation without any core change."**
   Tested by manually constructing a merged `OCOMObject` via its plain
   pydantic constructor (`evidence=obj_a.evidence + obj_b.evidence`)
   in tests, and via a get-then-save pattern around the unchanged
   `Storage` interface.
   **Confirmed** — but only demonstrated inside tests, not as a
   reusable pipeline component. See temporary decisions below.

## Decisions Considered Stable

These have survived every phase of this milestone unchanged and should
require a new ADR to change, not an incidental edit:

- **`OCOMObject`** (`core/object.py`) — field set (identity, object_type,
  metadata, classification, relationships, lifecycle_state, owner,
  governance, evidence) grounded in Meta/Object.md.docx's Core
  Characteristics.
- **`Evidence`** (`core/evidence.py`) — structurally separate from
  `metadata`, one entry per supporting source/fragment.
- **The three interfaces** (`interfaces/adapter.py`,
  `interfaces/normalizer.py`, `interfaces/storage.py`) — the seams
  every future source and every future storage backend must be built
  against.
- **Package boundary**: `adapters/`, `normalizers/`, `storage/` as
  separate, independently replaceable packages, documented in
  [ADR-001](ADR-001-normalizer-architecture.md).
- **pydantic as the modeling tool** for `OCOMObject`/`Evidence` and for
  validating LLM structured output (`ExtractionResult`).

## Decisions Considered Temporary

Explicitly not final architecture — expected to change once a second
real source or the OCOM Agent phase puts real pressure on them:

- **`LocalJSONStorage`** — one JSON file per object, full directory
  scan for `list()`, no indexing, no concurrency handling. Fine for a
  single-source prototype; not sufficient for an Agent that needs to
  search.
- **Identity resolution inside `LLMDocumentNormalizer`**
  (`_slugify(result.concept)`) — works only because it is a
  deterministic function of the LLM's own output string, with no
  registry of previously seen objects to resolve against. Flagged in
  ADR-001 as the wrong long-term location; recommended home is a
  future Registry-backed Knowledge Layer, built alongside OCOM Agent
  v0.1, not before.
- **Merge-on-save logic** — the get-then-save pattern that combines
  evidence for a shared identity exists only inside test code
  (`test_llm_normalizer_same_object_recognition.py`), not as a
  reusable pipeline component or in `main.py`.
- **`AnthropicLLMClient`** — minimal, un-exercised against a real API
  call, no retry or malformed-response handling beyond what
  `ExtractionResult` validation catches.
- **Python 3.9 target** — chosen because it is what is installed on
  this machine, not a considered long-term constraint.
- **Single-source coverage** — every claim about "a source can be
  swapped without touching the core" rests on one concrete source
  (local filesystem documentation). It is architecturally sound but
  has exactly one data point; a second real source (per
  [ADR-001](ADR-001-normalizer-architecture.md)'s Future Direction)
  is the next real test of it, not this milestone.

## What This Milestone Does Not Claim

This freeze does not claim the AI extraction is accurate, that
identity resolution is solved, or that the architecture has been
proven against more than one source. It claims the seams are in the
right place and, so far, have not needed to move.
