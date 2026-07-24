# MILESTONE-014: Better Retrieval

**Date:** 2026-07-24
**Status:** Frozen — three new, fully explainable ranking signals; still deterministic, no semantic search, no embeddings, no LLM.
**Builds on:** [MILESTONE-014-DESIGN.md](MILESTONE-014-DESIGN.md), [MILESTONE-008](MILESTONE-008.md), [MILESTONE-009-010](MILESTONE-009-010.md)

## Objective

Improve ranking quality with new signals, every one grounded in
already-indexed data, every one with a fixed documented weight, every
one rendered through the existing `MatchReason`/`explain()` machinery
unchanged. "Better ranking is desired, hidden ranking is not."

## Implemented Components

| Component | File | Status |
|---|---|---|
| `identifier_match` signal | `retrieval/retrieval_engine.py` | New |
| Frequency-aware `preview_match` (capped) | `retrieval/retrieval_engine.py` | Revised |
| `importance` signal (`_importance_reasons`) | `retrieval/retrieval_engine.py` | New |
| `SCORE_WEIGHTS` additions, `PREVIEW_FREQUENCY_CAP`, `IMPORTANCE_REFERENCE_CAP` | `retrieval/ranking.py` | Revised |
| `REASON_TEMPLATES` additions | `composer/formatter.py` | Revised |
| `TEXT_REASON_KINDS` addition | `composer/answer_composer.py` | Revised |

`indexer/`, `registry/`, `loader/`, `persistence/`, `reader.py`,
`cli.py`, `interactive.py`, `commands.py`, and every M001-M005 package
— all unchanged, confirmed via `git diff --stat` (empty for every one
of them). Only `retrieval/` (M008's own files) and `composer/`'s two
small lookup tables (M009-010's own files) were touched — exactly
where "Better Retrieval" should live.

## Signal Mapping (what was and wasn't added, and why)

The task suggested ten possible signals. Full reasoning is in
MILESTONE-014-DESIGN.md; summary:

| Suggested | Outcome |
|---|---|
| Exact title match, heading match | Already existed — unchanged. |
| Object identity match, alias match, path relevance | **Merged into one new signal: `identifier_match`.** `DocumentIndexEntry.id` and `.path` are the same value in this indexer (verified, not assumed), so treating identity/alias/path as three signals would triple-count one string. No separate alias field exists — M007 deliberately kept `RegistryEntry` to 3 pointer-only fields. |
| Keyword frequency | **New**, scoped to `preview_match` only (title/heading are short, single-mention fields; preview is the only body-text proxy M006 indexes at all). |
| Relationship proximity | Already satisfied — multi-relation documents already accumulate multiple reasons (M008). Not extended past one hop; that boundary wasn't in scope here. |
| Lifecycle references | **Not applicable** — no lifecycle concept exists anywhere in this data model (that's the unrelated OCOM-domain-object Agent pipeline's vocabulary — see MILESTONE-009-010.md's naming-collision note). Not invented without real data behind it. |
| Architecture references | Already existed (`builds_on`/`architecture_sequence`/`references`) — unchanged. |
| Document importance | **New: `importance`** — a literal, deduplicated inbound-reference count from `KnowledgeRegistry.relations`, not a guessed per-`document_type` table. |

## New Signals

### `identifier_match`

A query token found as a substring of `document.id.lower()` (also the
path). Lets `"milestone-003"` find `docs/architecture/MILESTONE-003.md`
directly even when its title never mentions "003" — verified as the
concrete motivating case, not a hypothetical.

### Frequency-aware `preview_match`

`_text_reasons` now counts real occurrences of each token in the
preview (`str.count()`), capped at `PREVIEW_FREQUENCY_CAP = 3`, emitting
that many `preview_match` reasons instead of always exactly one. Named
explicitly as scoped to preview text only — this is not full-document
search; M006 never indexed full document bodies.

### `importance`

One `MatchReason(kind="importance", detail=referencing_registry_id)`
per distinct document that references this one in
`KnowledgeRegistry.relations` (deduplicated by source — two relation
kinds from the same document count once), capped at
`IMPORTANCE_REFERENCE_CAP = 3`. Applied to every match — primary or
secondary — after it's already been found, never used to find one:
`test_importance_never_creates_a_match_on_its_own` confirms a
heavily-referenced but query-irrelevant document still never appears
in results. This is what keeps it from being "hidden ranking."

## Weight Table (final)

| kind | weight | note |
|---|---|---|
| `title_match` | 10.0 | unchanged |
| `identifier_match` | 8.0 | new |
| `heading_match` | 5.0 | unchanged |
| `builds_on` | 3.0 | unchanged |
| `architecture_sequence` | 2.0 | unchanged |
| `preview_match` | 2.0 | unchanged (now up to 3×) |
| `importance` | 0.5 | new — deliberately small, a tie-breaker, never able to outweigh one `title_match` |
| `references` | 1.0 | unchanged |

## Test Results

- `tests/test_retrieval_engine.py`: **48 passed** (35 before this
  milestone). 13 new: `identifier_match` (found by filename alone,
  case-insensitive, counts as a real primary match), `preview_match`
  frequency (counts real occurrences, respects the cap), `importance`
  (distinct-source deduplication, the cap, never creating a match on
  its own, absent when there are no inbound references), a
  weight-table-sums-correctly check, and two ambiguous-query tests
  (an exact identifier match outranks generic partial matches; a
  single strong text match outranks several small importance/reference
  signals with no text match at all). Two existing M008 tests
  (`test_a_document_related_through_two_relations_gets_both_reasons`,
  `test_explain_renders_each_reason_as_a_readable_line`) were updated
  to reflect real, expected new reasons on their fixtures — not
  regressions, re-verified against actual computed output before
  changing the assertions.
- Full suite: **254 passed** (241 before this milestone + 13 new), no
  other test file required changes.

## Real-Repository Verification (Before/After)

Ran manually against three repositories before finalizing any test:

| Repository | Result |
|---|---|
| `OCOM-Reader` | Deterministic across repeated `retrieve()` calls; no Index/Registry mutation; `"milestone-003"` now correctly ranks `MILESTONE-003.md` first (score 47.5) above generically-matching `MILESTONE-007.md`/`MILESTONE-012.md` (score 34.5 each) — impossible before this milestone, since no signal previously looked at the filename at all. |
| `/Users/mac/Downloads/OCOM` (366 docs) | 53 matches for `"architecture"`, deterministic, `identifier_match` correctly firing for path-segment hits like `docs/Reference Architecture/...`. |
| `/Users/mac/OCOM.wiki` (7 docs) | 1 match for `"architecture"`, deterministic, correctly shows no `importance` signal (no relations exist in this small flat repository — consistent with M011's own findings there). |

**Before/after, concretely:** prior to this milestone, a query
matching only a document's filename (not its title, headings, or
preview) produced zero matches — the exact `"milestone-003"` case
above returned no results at all in M008/M009-010. It now returns the
correct document, ranked first. Documents that are structurally
central (referenced by several others) now rank measurably higher
among otherwise-equally-relevant results, verified directly via the
`importance` reason list on real repository data (e.g.
`ADR-005-identity-resolution-signal-model.md` gaining three
`importance` reasons when queried).

## Known Limitations

- **`identifier_match` inherits M008's substring-matching limitation.**
  A short, generic token like `"milestone"` matches every
  `MILESTONE-*` document's identifier equally; only a more specific
  token (the actual number) differentiates them via score. Observed
  directly on the real repository (`"milestone-003"` still returns 32
  matches, correctly ranked, not a smaller precise set) — not a new
  problem this milestone introduced, but newly visible through the new
  signal. Not fixed here; word-boundary or phrase matching remains
  out of scope, as it was for M008.
- **`importance` is repository-relation-based, not usage-based** — it
  measures how many documents reference another in `KnowledgeRegistry`,
  not how often a document is actually read or searched for. A
  legitimate, defensible proxy, not a claim of "true" importance.
- **Frequency counting is preview-only**, per M006's own scope
  boundary (no full-document-body indexing exists to count against).
- **No `document_type` weighting was added**, again — still no
  grounded evidence for a specific per-type weight; `importance`
  (usage of the document by other documents) was judged the more
  defensible "document importance" proxy available from real,
  already-indexed data.

## Roadmap

```
✅ M001-M013 — OCOM Reader MVP + Repository Independence (frozen)
✅ M014 Better Retrieval — this document

🔄 M015-017 Product Experience & Extensibility (next)
⬜ M018 Web UI
⬜ M019 Optional LLM Layer
⬜ M020 Product Release
```
