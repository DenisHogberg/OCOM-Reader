# ADR-002: Boundaries Discovered by the Agent v0.1 First Vertical Slice

**Status:** Accepted
**Date:** 2026-07-23
**Applies to:** `agent/query.py`, `agent/registry.py`, `agent/evidence.py`, `agent/answer.py`
**Builds on:** [OCOM Agent v0.1 Design](OCOM-Agent-v0.1-Design.md), [ADR-001](ADR-001-normalizer-architecture.md), [MILESTONE-001](MILESTONE-001.md)

## Context

The first working Agent pipeline was implemented as a minimal vertical
slice, deliberately excluding vector search, embeddings, an LLM, and
`IdentityResolver`, to answer one question before building anything
else: can the Agent answer strictly from `Evidence`?

```
Query
 ↓
Registry
 ↓
Evidence Aggregation
 ↓
Answer Composer
```

Concretely: `Query` (`agent/query.py`) is a plain question, `ObjectRegistry.
find_candidates()` (`agent/registry.py`) does a keyword-overlap scan
over `Storage.list()`, `EvidenceAggregator.aggregate()` (`agent/evidence.py`)
unions the `Evidence` of every candidate returned, and `AnswerComposer.
compose()` (`agent/answer.py`) turns that into a template-based answer —
or an explicit refusal if no `Evidence` was found. Three tests exercise
this end to end, including the refusal path.

This ADR exists because that slice did what it was built to do:
generate real, code-backed information about where this architecture's
next real seam is, rather than a guess. Recording it now, before adding
anything, is the point — this is the same discipline used after
Reasoning Consistency Test v0.1 ([MILESTONE-001](MILESTONE-001.md)),
applied one layer up.

## Confirmed Decisions

These held up under a working implementation, not just under design:

- **The Agent operates entirely on top of `Storage`.** Nothing in
  `agent/` imports `Adapter` or any `Normalizer`. It only ever reads
  what Reader already produced.
- **The Core Object Model did not change.** `core/object.py`,
  `core/evidence.py`, and every file under `interfaces/` have zero
  diff from this phase (verified by `git diff --stat`, not assumed).
- **`Evidence` is the only source of grounding.** `AnswerComposer`
  builds its answer text and its `sources` list exclusively from
  `Evidence.excerpt` / `Evidence.reference`. Nothing derives an answer
  from `OCOMObject.metadata` alone.
- **An answer without `Evidence` is refused, not degraded.** When
  `UnifiedEvidenceContext.evidence` is empty, `AnswerComposer` returns
  `grounded=False` and a fixed refusal string — there is no code path
  that falls back to describing an object from its metadata. This was
  the one invariant this slice existed to prove, and it holds.
- **A template-based `AnswerComposer`, with no LLM, was sufficient to
  prove that invariant.** Open Question 5 in the Design doc
  ("Is an LLM required in AnswerComposer?") is answered, for v0.1:
  no. Whether one is *wanted* later for phrasing is a separate,
  smaller question than whether one was *needed* to prove grounding.

## Discovered Limitations

These are not defects in what was asked for — the slice was scoped to
surface exactly this kind of gap rather than hide it:

- **`Registry` without Identity Resolution returns candidates, not
  objects.** `find_candidates()` has no way to know whether two
  matches are the same real-world object, near-duplicates, or
  genuinely unrelated things that happen to share a keyword. It
  returns everything that matched and stops there — resolution was
  never its job.
- **Evidence aggregation across *all* candidates is temporary
  behavior, not a design choice.** `EvidenceAggregator.aggregate()`
  unions `Evidence` from every object `Registry` returns, with no
  check that they represent the same thing. `test_answer_cites_
  evidence_from_every_matching_object` demonstrates this directly: two
  unrelated-but-keyword-matching objects produce one blended answer.
  This is the concrete instance of exactly the risk named in
  [OCOM-Agent-v0.1-Design.md §7](OCOM-Agent-v0.1-Design.md#7-evidence-handling)
  ("Unified Object View" assumes a resolved canonical identity) —
  the design doc predicted this gap before code existed; the slice
  confirmed it exists in practice.
- **Keyword search is a placeholder, not a search strategy.**
  `ObjectRegistry._matches()` does raw substring/word-overlap matching
  with no stopword filtering and no punctuation stripping — a term
  like `"object?"` from `"What is OCOM Object?"` fails to match
  anything, and the query only succeeds because another term
  (`"ocom"`) happens to match instead. It works for the one scenario
  it was built for and is not expected to generalize.
- **There is no ranking.** `find_candidates()` returns every match in
  storage order, with no relevance ordering and no limit. This does
  not yet matter at the current data volume, and is not being fixed
  now.

## Decision

The next required component, before any further investment in the
Answer layer (phrasing, LLM-based composition, richer templates), is
the **Identity Resolution Layer** already specified in
[OCOM-Agent-v0.1-Design.md §6](OCOM-Agent-v0.1-Design.md#6-identity-resolution-strategy).

This is not a new decision — the Design doc named this dependency
before implementation started ("Identity Resolution... deliberately
deferred... confirmed absent from `LLMDocumentNormalizer`"). What
changed is that it is no longer a predicted gap: `test_answer_cites_
evidence_from_every_matching_object` is code-level proof that
`EvidenceAggregator` blends unrelated objects without it. Improving
`AnswerComposer` further — templates, LLM phrasing, richer statements
— without first bounding what `EvidenceAggregator` is allowed to
combine would be building on top of a component known to
over-aggregate. Identity Resolution is what turns "a list of keyword
matches" into "the object (or objects) this question is actually
about," and every downstream layer depends on that distinction being
made correctly, not assumed.

No implementation is proposed by this ADR. It records why the next
implementation task, when it happens, should be `IdentityResolver`
before `AnswerComposer` v0.2.
