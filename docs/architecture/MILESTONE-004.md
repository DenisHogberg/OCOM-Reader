# MILESTONE-004: OCOM End-to-End Reasoning Path v0.1

**Date:** 2026-07-23
**Status:** Frozen — first complete `Document → Answer` loop, proven by real execution, not by asserting the pieces should compose.
**Builds on:** [Architecture-Status-v0.1](Architecture-Status-v0.1.md), [ADR-001](ADR-001-normalizer-architecture.md) through [ADR-006](ADR-006-classification-lifecycle-and-human-override.md), [OCOM-Classification-Engine-v0.1](OCOM-Classification-Engine-v0.1.md), [OCOM-Identity-Resolution-v0.1](OCOM-Identity-Resolution-v0.1.md)

## What Was Integrated

A new package, `runtime/` (`context.py`, `pipeline.py`), coordinates seven
previously-independent, previously-untested-together components into
one path:

```
Document → Adapter → RawDocument → Normalizer → OCOMObject
  → ClassificationEngine.classify() → apply_classification()
  → IdentityResolver.resolve() (folded across Storage, see below)
  → Storage.save()
  → Registry.find_candidates() → EvidenceAggregator.aggregate()
  → AnswerComposer.compose() → Answer
```

`runtime/pipeline.py` makes no classification, identity, or grounding
decision itself — every one of those still comes from the same
component that was independently validated for it
(`ClassificationEngine`, `IdentityResolver`, `AnswerComposer`). What it
owns is call order and one genuinely new piece of coordination logic:
folding `IdentityResolver`'s pairwise-only comparison (`resolve(a, b)`)
into a decision against a whole `Storage` — nothing before this
milestone did that. See "New Assumptions Discovered" below for why
that fold is flagged, not just quietly shipped.

Three scenarios proven by actual execution
(`tests/test_end_to_end_reasoning_path.py`), not by inspection:

1. **Full happy path** — a document is ingested, classified (`Role`,
   `Marketing`, `Partner Management` all correctly proposed), finds no
   prior match (`NEW`, empty `Storage`), and a later question about it
   returns `grounded=True` citing the real source file.
2. **Unknown object** — a question with no vocabulary overlap with
   anything in `Storage` returns `grounded=False`, the fixed refusal
   text, and an empty `sources` list. No hallucination path exists to
   trigger.
3. **Identity conflict** — two documents describing plausibly-the-same
   role (`Affiliate Manager` / `Affiliate Manager EU`) produce
   `UNCERTAIN`, `matched_object_id=None`, and both are persisted as
   separate objects — confirmed via `Storage.list()`, not assumed from
   the decision alone.

## What Remained Unchanged

Confirmed by `git diff --stat`, not asserted: `core/`, `interfaces/`,
`storage/`, `identity/`, `intelligence/`, `agent/`, `adapters/`,
`normalizers/` — zero diff. Every component this milestone uses was
called through its existing public interface, exactly as already
tested in isolation. `runtime/` is additive only.

## New Runtime Boundary

`runtime/` sits beside `agent/`, `identity/`, `intelligence/` — not
inside any of them, not a new layer any of them depends on. It is the
first package in this project whose *entire* job is calling other
packages; it owns no model, no decision rule, no persistence format of
its own. `RuntimeContext` (`context.py`) is a plain construction
convenience (one instance of each collaborator), not a component with
behavior.

## New Assumptions Discovered

Findings from actually chaining components that no isolated test could
have surfaced:

1. **The pairwise-to-storage fold is a new, previously-undecided rule,
   not a re-application of an existing one.** `_resolve_against_storage()`
   in `pipeline.py` compares a candidate against every stored object of
   the same `object_type` and picks: first `MATCH` wins; else first
   `UNCERTAIN` wins; else `NEW`. No prior document specified this —
   [OCOM-Identity-Resolution-v0.1.md](OCOM-Identity-Resolution-v0.1.md)'s
   Implementation Status section already noted the
   `ResolutionRequest`/batch contract was never built, and this is the
   concrete gap that left: something had to decide how N pairwise
   comparisons become one outcome, and nothing before this milestone
   did. Flagged here rather than presented as settled.

2. **MILESTONE-003's classic "Affiliate Manager vs. Partner Manager"
   pairing does not reproduce `UNCERTAIN` through the real, chained
   pipeline.** That result depended on both fixtures being given
   *identical, hand-set* `classification` lists
   (`["Marketing", "Partner Management"]` on both). Run through the
   actual `ClassificationEngine`, "Partner Manager" only ever gets
   `category: "Partner Management"` (the `"partner"` keyword) — never
   `domain: "Marketing"` (needs `"affiliate"`, which "Partner Manager"
   doesn't contain). The real classification sets only overlap at
   0.67, not 1.0, and the combined score (0.47) lands just *below*
   `UNCERTAIN_THRESHOLD`, not above it — the real pipeline returns
   `NEW` for that exact pair, not `UNCERTAIN`. This milestone's Test 3
   uses a pair verified against the real chain instead
   (`"Affiliate Manager"` / `"Affiliate Manager EU"`, confirmed
   `UNCERTAIN` at 0.67 by actually running it, not by re-using an
   isolated-experiment fixture). **Isolated-component results do not
   automatically compose — this is the concrete proof, not a
   suspicion.**

3. **`Registry`'s un-migrated keyword search can leak Python dict
   internals into search matches.** `ObjectRegistry._searchable_text()`
   still stringifies raw `metadata` dicts
   (already flagged as pending in
   [ADR-003](ADR-003-metadata-semantic-boundary.md#consequences),
   [ADR-004](ADR-004-metadata-namespace-migration.md#4-compatibility-impact),
   [ADR-006](ADR-006-classification-lifecycle-and-human-override.md#5-impact-on-agent-and-identity-resolution)).
   Concretely reproduced during this milestone's setup: a query
   containing the literal word `"concept"` matched an object purely
   because `str({"concept": "Affiliate Manager"})` contains the
   substring `"concept"` as a dict-repr artifact — the *key name*, not
   any actual content, produced the match. Also reproduced: a query
   for `"Payment Manager"` matched an `"Affiliate Manager"` object via
   the single-letter/common-word terms `"a"` and `"is"`, which are
   substrings of almost anything. Both are named, not fixed — fixing
   `Registry` is out of scope for this milestone (constraints: no
   optimization) and was already scoped as its own pending task before
   this milestone started.
4. **`AnswerComposer`'s `sources` list mixes real references with
   synthetic ones, and this milestone is the first place that became
   externally visible.** Once `ClassificationEngine` enriches an
   object, its `Evidence.reference` points at the *upstream*
   `Evidence.identity` (`OCOM-Object-Intelligence-v0.1.md` §5.4's own
   decision, correctly implemented) rather than a file path. A real
   `ask()` answer's `sources` list therefore contains both
   `.../AffiliateManager.md` and strings like
   `evidence:fsdoc:35cc1254c5c7c489` side by side. Architecturally
   correct (the derivation chain is genuinely preserved) but a rough
   edge for anything presenting `sources` to a person — worth naming
   for whoever builds a real answer-rendering surface next.

## Remaining Gaps

Not fixed, per this milestone's own "do not optimize" constraint —
named so they aren't rediscovered from scratch:

- `Registry` keyword search remains un-migrated (finding 3) — same gap
  named three times before this milestone, now with a concrete,
  reproduced failure case attached to it.
- The pairwise-fold rule (finding 1) has no test proving it's the
  *right* fold, only that it's *a* consistent one — e.g. "first MATCH
  wins" versus "highest-confidence MATCH wins" was never compared.
- `IdentityResolver`'s scoring still runs the pre-ADR-005 linear
  formula ([Architecture-Status-v0.1](Architecture-Status-v0.1.md)
  already lists this as Experimental) — this milestone exercises it
  as-is and surfaces no new evidence either way about the undelivered
  three-band model.
- No lazy/on-demand enrichment: `ingest_document()` always classifies,
  matching [OCOM-Object-Intelligence-v0.1.md](OCOM-Object-Intelligence-v0.1.md#architectural-questions--answered)'s
  ingestion-time-only decision — its on-demand alternative remains
  undesigned.

## What This Milestone Does Not Claim

This does not claim `IdentityResolver`'s scoring is well-calibrated,
that `Registry`'s search is adequate beyond this milestone's narrow
test vocabulary, or that the pairwise-fold rule is the correct one long
term. It claims a document can now travel, through real code, from raw
text to a cited, refusal-capable answer — and that doing so surfaced
concrete, reproducible facts three isolated-component milestones could
not have found.
