# MILESTONE-002: OCOM Agent v0.1 — First Vertical Slice Freeze

**Date:** 2026-07-23
**Status:** Frozen — this document marks the second architectural milestone, closing the first Agent implementation phase before Identity Resolution work begins.
**Builds on:** [MILESTONE-001](MILESTONE-001.md), [OCOM Agent v0.1 Design](OCOM-Agent-v0.1-Design.md), [ADR-002](ADR-002-agent-vertical-slice-boundaries.md)

## What's Proven

- **`OCOMObject`/`Evidence` support a real consumer, not just a
  producer.** Reader (MILESTONE-001) proved these models could be
  built and stored. This milestone proves they can be *read back* and
  turned into an answer by code that never saw how they were created —
  `agent/` has no dependency on `adapters/` or `normalizers/`.
- **"Never answer without Evidence" is enforceable in code, not just
  in prose.** `AnswerComposer.compose()` has exactly one branch when
  `UnifiedEvidenceContext.evidence` is empty, and it is a refusal.
  `test_answer_is_not_grounded_when_no_evidence_found` exercises it.
- **A full Question → Object → Evidence → Answer pass works
  end-to-end without an LLM, a vector database, or embeddings.** Three
  tests, zero new dependencies, zero changes to `core/`, `interfaces/`,
  or `storage/`.
- **The Agent layer can be built incrementally, the same way Reader
  was**, in small, independently-testable pieces (`Query`, `Registry`,
  `EvidenceAggregator`, `AnswerComposer`) rather than as one large
  component. This was a working method being tested as much as an
  architecture.

## What Turned Out to Be a Limitation

Documented in full in [ADR-002](ADR-002-agent-vertical-slice-boundaries.md);
summarized here:

- `ObjectRegistry.find_candidates()` returns keyword matches, not
  resolved objects — it has no way to tell "the same thing described
  twice" from "two different things that share a word."
- `EvidenceAggregator` aggregates across *every* candidate returned,
  which a dedicated test now demonstrates blends unrelated objects'
  evidence into one answer when more than one candidate matches.
- Keyword search (`_matches`) is a placeholder: no punctuation
  stripping, no stopword handling — it happened to work for the one
  scenario it was built for.
- No ranking exists; `find_candidates()` returns matches in storage
  order with no relevance signal or limit.

None of these are being fixed in this milestone. They are the
concrete, code-confirmed version of gaps the
[Agent Design doc](OCOM-Agent-v0.1-Design.md) already predicted before
any of this was implemented.

## Hypotheses Confirmed

From the Design doc's open questions and stable/hypothesis split
(carried over from the prior phase's review):

1. **"A template-based composer is sufficient to prove the
   never-answer-without-evidence contract before adding
   natural-language phrasing."** (Design doc, Open Question 5) —
   **Confirmed.** No LLM was needed to prove grounding.
2. **"Registry can be built as a thin wrapper over `Storage` with no
   new database."** — **Confirmed**, though only at the scale this
   milestone tested; a full `Storage.list()` scan remains an accepted,
   unaddressed limitation (same one already named for `LocalJSONStorage`
   in MILESTONE-001).
3. **"Identity Resolution cannot be skipped or deferred indefinitely
   once real aggregation is attempted."** — **Confirmed**, earlier
   than expected. This was predicted as a Phase-2-or-later concern in
   the Design doc; a single test in this milestone (`test_answer_cites_
   evidence_from_every_matching_object`) was enough to demonstrate it
   is already load-bearing at the first working pass, not a
   theoretical future problem.

## What Experiments Are Needed Next

Not decisions — open questions that need real behavior to answer, not
more design:

1. **What does `IdentityResolver.resolve()` actually do with two
   candidates from `find_candidates()` that share a keyword but are
   not the same object?** The Design doc's exact-match-on-`metadata
   ["concept"]` strategy (§6) was written for ingestion-time matching
   (Normalizer output vs. Registry). Whether the same strategy applies
   cleanly at query-time, over `Registry.find_candidates()`'s looser
   keyword-match output, is untested and may not transfer directly.
2. **Does fixing keyword search (stopwords, punctuation) meaningfully
   change how often multiple unrelated candidates match at once** —
   or is that purely an `IdentityResolver` problem regardless of how
   clean the initial candidate list is? Needs a second, less
   synthetic test corpus to answer honestly.
3. **Should `IdentityResolver` be invoked inside `Registry.
   find_candidates()`, or as a separate step the caller applies
   afterward (as sketched in the Design doc's query-time data flow,
   §5.2)?** The vertical slice's four-module structure
   (`query` / `registry` / `evidence` / `answer`) doesn't yet have an
   obvious fifth slot; where `IdentityResolver` is called from is an
   implementation question the next phase needs to settle, not this
   one.
4. **Is a "no relevant evidence for this specific object" answer
   different enough from "no such object at all" to need distinct
   handling in `AnswerComposer`**, once `IdentityResolver` can tell
   those two cases apart? Currently indistinguishable, noted but not
   resolved.
