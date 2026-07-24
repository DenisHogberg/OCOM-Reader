# MILESTONE-014: Better Retrieval — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the established workflow.
**Builds on:** [MILESTONE-013](MILESTONE-013.md), [MILESTONE-008](MILESTONE-008.md), [MILESTONE-009-010](MILESTONE-009-010.md)

## Objective

Improve ranking quality with new, real signals — every one grounded in
data this pipeline already has, every one with a fixed, documented
weight, every one rendered through the existing `MatchReason`/`explain()`
machinery unchanged. No signal is added that can't be pointed at and
explained; "better ranking is desired, hidden ranking is not."

## Mapping the Suggested Signals to What Actually Exists

The task listed ten possible signals. Each is addressed on its own
merits — including the ones this milestone deliberately does **not**
add, and why.

| Suggested signal | Decision |
|---|---|
| Exact title match | Already exists (`title_match`, M008) — unchanged. |
| Heading match | Already exists (`heading_match`, M008) — unchanged. |
| Object identity match | **New: `identifier_match`.** See below. |
| Alias match | Folded into `identifier_match` — see below; no separate alias field exists (M007 deliberately kept `RegistryEntry` to exactly 3 pointer-only fields, no `name`/`aliases`). |
| Keyword frequency | **New**, scoped to `preview_match` only — see below. |
| Relationship proximity | Already satisfied: a document connected to a primary match via multiple relations already accumulates multiple reasons and a higher score (M008's per-reason summation). Not changed further — extending beyond one hop would revisit M008's own deliberate boundary, which this milestone wasn't asked to do. |
| Lifecycle references | **Not applicable.** No lifecycle concept exists anywhere in `indexer/`/`registry/`'s data model (that's an OCOM-domain-object concept from the unrelated M002-M005 Agent pipeline — see MILESTONE-009-010.md's naming-collision note). Inventing one here would be exactly the kind of ungrounded feature this project has repeatedly declined to add without real data behind it. |
| Architecture references | Already exists (`architecture_sequence`, `builds_on`, `references` relation kinds, M007/M008) — unchanged. |
| Document importance | **New: `importance`.** See below. |
| Path relevance | Folded into `identifier_match` — see below. |

## `identifier_match` (covers identity, alias, and path relevance)

`DocumentIndexEntry.id` and `.path` are the same value in this
indexer's current implementation (`MetadataExtractor.document_id()`
returns `relative_path.as_posix()`, identical to `.path`) — verified
directly, not assumed. Treating "matches the document's id/filename"
and "matches its path" as two separate signals would double-count the
exact same string. One new signal instead: a query token found as a
substring of `document.id.lower()` (which is also the path) produces a
`MatchReason(kind="identifier_match", detail=token)`. This is what
lets a query like `"milestone-003"` find `docs/architecture/MILESTONE-003.md`
directly even when its title ("Identity Resolution — Experiment
Findings") never mentions "003" — the concrete case this signal exists
for.

If `.id` and `.path` ever diverge in a future milestone, this decision
should be revisited; not something to design around speculatively now.

## `importance` (document-level, query-independent)

How many other documents reference a given one — a simple, literal
inbound-reference count from `KnowledgeRegistry.relations` (any
relation type, deduplicated by source document, since one document
referencing another via two relation kinds shouldn't count twice).
This is the plain, explainable proxy for "importance" available from
already-indexed structural data — not a per-`document_type` weight
table (ADR vs. Milestone vs. README), which M008/M009-010 both
explicitly declined to invent without evidence, and which this
milestone doesn't have new evidence for either.

Represented the same way every other signal is: one
`MatchReason(kind="importance", detail=referencing_registry_id)` per
distinct referencing document, capped, so `explain()` shows exactly
*which* documents make this one "important" — not just a bare number.

**Critical invariant:** importance is added to a match's existing
`reasons` — it never creates a match on its own. A highly-referenced
document that doesn't match the query text or relation graph at all
still never appears in results. Importance only reorders documents
already legitimately surfaced; it cannot pull in unrelated ones. This
is what keeps it from being "hidden ranking."

## Keyword Frequency (scoped to `preview_match` only)

`preview` is the only body-text proxy this indexer has (M006's own
scope boundary — full document content was never indexed). Counting
occurrences in `title`/`heading` text is not meaningful (both are
short, essentially single-mention fields); `_text_reasons` is extended
to count real occurrences of each token in `preview_lower` via
`str.count()`, capped, emitting that many `preview_match` reasons
instead of always exactly one. A token appearing three times in a
preview now outweighs one appearing once — real, honestly-scoped
frequency, not a claim of full-text search.

## Weight Table (revised)

| kind | weight | change |
|---|---|---|
| `title_match` | 10.0 | unchanged |
| `identifier_match` | 8.0 | **new** — strong signal (the query names the document directly), just under `title_match` |
| `heading_match` | 5.0 | unchanged |
| `builds_on` | 3.0 | unchanged |
| `architecture_sequence` | 2.0 | unchanged |
| `preview_match` | 2.0 | unchanged (now possibly repeated up to the frequency cap) |
| `importance` | 0.5 | **new** — deliberately small; a tie-breaker among already-relevant documents, never able to outweigh a single `title_match` |
| `references` | 1.0 | unchanged |

Frequency cap (`preview_match` repeats) and importance cap (distinct
referencing documents counted) are both **3** — small, round, and
explicitly chosen so neither signal can runaway-dominate a result
purely from a repetitive preview or a heavily-cross-referenced
document; a real number, not a magic one, and named as such.

## Explainability

`composer/formatter.py`'s `REASON_TEMPLATES` gains two entries:

```python
"identifier_match": "Matches document identifier: {detail}",
"importance": "Referenced by: {detail}",
```

`composer/answer_composer.py`'s `TEXT_REASON_KINDS` gains
`"identifier_match"` (a match found only by identifier is still
"evidence," not "related" — it directly matched the query, just via a
different field). `"importance"` is deliberately **not** added to
`TEXT_REASON_KINDS` — it is a modifier present on both evidence and
related documents alike, never itself a reason a document counts as
directly matching the query.

## Determinism and Reproducibility

Unchanged mechanism: `Ranker.rank()` still sums fixed weights and
breaks ties by `registry_id`. Every new signal is computed the same
deterministic way as the existing ones (substring checks, relation
lookups) — no randomness, no external state, no LLM.

## Regression Risk

Every existing score in `test_retrieval_engine.py`/`test_answer_composer.py`/`test_reader_pipeline.py`
that hardcodes an exact score or reason list will change (new
documents may now qualify as `identifier_match`; nearly every real
document gains `importance` reasons once real relations exist). These
tests are expected to need updating, not indicative of a regression —
each will be re-verified against real, freshly-computed values before
being changed, the same "recompute, don't guess" discipline used
throughout this project (e.g. MILESTONE-004's corrected fixture).

## Test Plan

- Unit: `identifier_match` fires/doesn't fire correctly; `preview_match`
  frequency counting and its cap; `importance` reason generation,
  deduplication by source document, and its cap; `importance` never
  creates a match on its own; weight table sums correctly for
  multi-signal matches.
- Determinism: repeated `retrieve()` calls identical; tie-breaking
  still by `registry_id`.
- Ambiguous query tests: a query that could plausibly match several
  documents at different strengths, confirming the new signals produce
  a defensibly different (not just differently-ordered-by-luck) result.
- Regression: full existing suite re-verified and updated where scores
  legitimately changed.
- Real-repository verification (before writing the above): run several
  queries against this project's own repository and at least one other
  real repository used in prior milestones, comparing before/after
  ranking and confirming `explain()` output stays fully readable.

Proceeding to implementation now.
