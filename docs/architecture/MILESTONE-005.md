# MILESTONE-005: OCOM Runtime v0.2 — Reliability Freeze

**Date:** 2026-07-23
**Status:** Frozen — this document closes the Runtime v0.2 reliability hardening phase before work begins on a real second source.
**Builds on:** [MILESTONE-004](MILESTONE-004.md), [OCOM-Runtime-v0.2-Reliability-Design](OCOM-Runtime-v0.2-Reliability-Design.md), [OCOM-Runtime-v0.2-Resolution-Evidence-Design](OCOM-Runtime-v0.2-Resolution-Evidence-Design.md)

## 1. Objective

MILESTONE-004 proved a document could travel end to end from raw text
to a cited answer — and, in doing so, produced four concrete,
reproduced reliability findings (metadata-key leakage into search,
short-token false positives, an unvalidated identity fold rule, and
confusing internal references in answers). Runtime v0.2 existed to
answer one question: can those four findings be closed with small,
independently-testable components, the same discipline this project
used for every prior layer, rather than papered over?

Concretely, Runtime v0.2 set out to prove:

- **Deterministic search** — a query either matches an object for a
  traceable, explainable reason, or it doesn't; no fuzzy or
  probabilistic behavior.
- **Controlled candidate discovery** — what is searchable is a
  decided, closed boundary (`identity`/`attributes` values), not
  whatever a naive `str(metadata)` happens to expose.
- **Safe ambiguity handling** — multiple plausible matches are
  surfaced, never silently resolved by picking one.
- **Evidence-based answers** — every answer still traces to real
  `Evidence`, and internal provenance mechanics stay internal.

## 2. Implemented Components

| Component | Status |
|---|---|
| QueryNormalizer | Implemented |
| SearchPolicy | Implemented |
| Registry Integration | Implemented |
| ResolutionPolicy | Implemented |
| EvidencePresentation | Implemented |
| Full regression | Passed |

Each was built as its own standalone, independently-tested unit under
`runtime/` (`runtime/query/`, `runtime/search/`, `runtime/resolution/`,
`runtime/evidence/`) before any wiring — the same "prove it alone
first" sequencing used for `identity/` and `intelligence/`. Full
regression is `tests/test_runtime_v0_2_regression.py`, exercised
through new, minimal orchestration (`runtime/scenario.py`) that wires
all four together without modifying any of them, `agent/`, `identity/`,
or `intelligence/`.

## 3. Confirmed Guarantees

### Search isolation

- Dict **key names** never participate in matching — only namespace
  **values** do. The exact MILESTONE-004 failure (`"concept"` matching
  via a dict-repr artifact) is closed and covered by a regression test
  (`test_no_metadata_key_leakage`).
- `metadata["technical"]` is excluded entirely, at every nesting depth
  — confirmed against both the simple flat shape and the real, nested
  `ClassificationEngine` output shape.

### Resolution safety

- Exactly one `MATCH` → accepted.
- More than one simultaneous `MATCH` → `UNCERTAIN`, never auto-ranked
  by confidence, never merged.
- A confident `MATCH` is not invalidated by an unrelated `UNCERTAIN`
  elsewhere in the same resolution pass — but that `UNCERTAIN` is
  recorded, never silently dropped.
- No automatic merge happens outside the single-`MATCH` case, in
  either the ingestion path (`runtime/pipeline.py`, pre-existing) or
  the query-time path (`runtime/scenario.py`, new this milestone) —
  confirmed by `test_ambiguous_identity_produces_uncertain_with_no_false_answer`,
  which checks `Storage` directly rather than trusting the returned
  decision alone.

### Evidence principle

- Answers are still composed only from `Evidence` — nothing new in
  Runtime v0.2 changed that invariant, established back in
  [ADR-002](ADR-002-agent-vertical-slice-boundaries.md).
- Provenance is not lost in presentation: `EvidenceView.original_id`
  always carries the real `Evidence.identity` a view was built from —
  confirmed by `test_original_evidence_is_left_unmodified`.
- The specific internal string named in this milestone's own scope
  (`Evidence.source` values like `"object-intelligence:classification-engine"`)
  is confirmed to never reach `Answer.sources`.

## 4. Known Limitations

### Evidence reference chain

```
classification evidence
        ↓
parent evidence reference
        ↓
human source
```

This chain does not resolve fully. `EvidencePresentationMapper` cleans
up `source_type` and filesystem paths, but a classification-derived
`Evidence.reference` (which points at another `Evidence.identity`, not
a location) is passed through unchanged — confirmed directly in this
milestone's regression run: `answer.sources` for an enriched object
contains both a clean filesystem path *and* a still-internal-looking
string like `evidence:role:affiliate-manager`. The narrower fix (`source`
never leaks) is real and tested; the fuller one (`reference` always
resolves to something human-facing) is not yet built.

### Query-time resolution

The current approach (`runtime/scenario.py`) is:

- treat the first candidate `Registry` returns as an anchor;
- compare every other candidate against it, pairwise.

This is not a clustering strategy. It answers "is candidate 2 the same
as candidate 1," not "which of these N candidates are mutually the
same object." Three or more genuinely-clustered candidates are not
handled correctly by this approach — it was never claimed to solve
that, only to make the two- and three-candidate scenarios this
milestone actually tested behave safely.

### Answer text sanitization

`Answer.sources` passes through `EvidencePresentationMapper`; the
generated `Answer.text` does not. `AnswerComposer.compose()`
(`agent/answer.py`, frozen throughout Runtime v0.2) builds its prose
directly from raw `Evidence` before any presentation mapping runs, so
an internal reference string can still appear inside the answer's body
text even when the `sources` list next to it is clean.

## 5. Stable Architecture After Runtime v0.2

Considered settled, requiring a new ADR to change:

```
QueryNormalizer
SearchPolicy
Registry boundary
ResolutionPolicy
Evidence presentation boundary
```

Each exists as an independent, standalone component with its own
tests, composed — not absorbed — by `Registry` and `runtime/scenario.py`.
None of `core/`, `interfaces/`, `storage/`, `identity/`, `intelligence/`,
or `agent/` changed at any point during Runtime v0.2 — confirmed by
`git diff --stat` at every step, not assumed.

## 6. Next Phase Proposal

**Phase: Real Knowledge Loop**

```
External Source
      ↓
Adapter
      ↓
Normalizer
      ↓
OCOM Object
      ↓
Registry
      ↓
Agent
```

Goal: the first real second source. Every claim this project has made
about swappable sources (`ADR-001`) and about search/resolution
generalizing beyond one synthetic corpus (MILESTONE-002's still-open
question) rests on a single source (local filesystem documentation).
Runtime v0.2 hardened what exists; it did not test it against anything
new. A real second source is the next thing that would actually test
these guarantees rather than confirm them again against the same data
shape.
