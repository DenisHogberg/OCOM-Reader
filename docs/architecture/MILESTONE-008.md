# MILESTONE-008: Retrieval Engine v0.1

**Date:** 2026-07-24
**Status:** Frozen — first working Retrieval Engine.
**Builds on:** [MILESTONE-007](MILESTONE-007.md) (Knowledge Registry), [MILESTONE-006](MILESTONE-006.md) (Repository Indexer)

## Objective

Answer, deterministically and explainably: *which documents and
relations are most relevant to this query, and why?* The Retrieval
Engine finds and ranks — it does not answer the user in natural
language. That is M009 (Answer Composer)'s job.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `QueryObject`, `MatchReason`, `RetrievalMatch`, `RetrievalResult` | `retrieval/models.py` | Implemented |
| `QueryParser` | `retrieval/query_parser.py` | Implemented |
| `Ranker` | `retrieval/ranking.py` | Implemented |
| `RetrievalEngine` | `retrieval/retrieval_engine.py` | Implemented |

No changes were required to `runtime/`, `registry/`, `indexer/`,
`core/`, `interfaces/`, `storage/`, `identity/`, `intelligence/`,
`adapters/`, `normalizers/`, or `agent/` — confirmed via
`git diff --stat` against all of them (empty). Unlike M007, this
milestone needed no extension to an existing package: `KnowledgeRegistry.relations`
was already a public field, sufficient for the retrieval algorithm below.

## Architecture

```
RepositoryIndex (M006, read-only)   KnowledgeRegistry (M007, read-only)
              │                              │
              └───────────────┬──────────────┘
                               ▼
                     RetrievalEngine(index, registry)
                               │
        raw query text ──► QueryParser ──► QueryObject (tokens)
                               │
                               ▼
                   ┌── primary matches ──┐   (text: title/heading/preview)
                   │                     │
                   └── secondary matches ┘   (relations: builds_on/references/architecture_sequence)
                               │
                               ▼
                            Ranker  (fixed-weight sum, deterministic tie-break)
                               │
                               ▼
                        RetrievalResult (ranked RetrievalMatch list)
```

`RetrievalEngine` is stateless: every `search()`/`retrieve()` call
re-derives its result from the `RepositoryIndex`/`KnowledgeRegistry` it
was constructed with. Neither is ever mutated — verified by
`model_dump()` equality before/after retrieval calls, both on a
synthetic fixture and on the real repository.

## Search Algorithm

Two-tier, both tiers fully explainable via `MatchReason`:

1. **Primary matches** — a document whose `title`, any `heading.text`,
   or `preview` contains a query token as a case-insensitive substring
   (`RepositoryIndex` data only). One `MatchReason` per (field, token)
   hit, so a document can accumulate multiple reasons.

2. **Secondary matches** — documents connected to a primary match by a
   `KnowledgeRelation` (`builds_on` / `references` / `architecture_sequence`)
   that did not themselves match the query text. Expansion is exactly
   **one hop** from primary matches only — a secondary match's own
   relations are never traversed, so results stay bounded and
   predictable.

   Expansion follows relations in **both directions**: if primary
   match `B` has `A --builds_on--> B` (something builds on `B`) or
   `B --builds_on--> C` (`B` builds on something), both `A` and `C`
   are surfaced as secondary matches. This was a deliberate deviation
   from the first implementation, found and fixed during real-repository
   verification (see Known Limitations / Design Decisions below) — an
   outbound-only reading was tried first and shown to be wrong on real
   data before any test was written.

No LLM, no embeddings, no semantic search, no fuzzy matching, no
stemming: every match is a literal substring check against already-extracted
Index data, and every relation comes unchanged from the Registry.

## Ranking Algorithm

Deterministic, fixed-weight sum — no probabilistic or learned model:

| Reason kind | Weight |
|---|---|
| `title_match` | 10.0 |
| `heading_match` | 5.0 |
| `preview_match` | 2.0 |
| `builds_on` | 3.0 |
| `architecture_sequence` | 2.0 |
| `references` | 1.0 |

A match's score is the sum of its reasons' weights. Ties are broken by
`entry.registry_id` (lexicographic) — a deterministic tie-break, not a
relevance judgment.

`document_type` (ADR vs. MILESTONE vs. README, etc.) is **deliberately
not** used as a scoring factor. No grounded weighting for "should an
ADR outrank a README, and by how much" exists yet, and inventing one
without evidence would repeat the exact mistake this project has
consistently avoided (e.g. ADR-005 leaving its own thresholds
explicitly unset rather than guessing). This is a named gap for a
future milestone, not an oversight.

## Explainability

`RetrievalEngine.explain(match)` renders each stored `MatchReason` as a
`"{kind}: {detail}"` line — e.g. `"title_match: runtime"`,
`"builds_on: docs/architecture/MILESTONE-003.md"`. No generated text
exists anywhere in `retrieval/models.py`: `MatchReason.detail` always
records a fact (the matched token, or the registry_id of the primary
match a relation came from), never composed prose. Formatting into a
human phrase (e.g. "Совпадение по названию.") is a presentation
concern for M009, deliberately kept out of this layer — the same
separation `EvidencePresentationMapper` established for evidence in
M005.

## Public API

```python
engine = RetrievalEngine(index, registry)
engine.search(query_text)      # -> list[RetrievalMatch], unranked
engine.retrieve(query_text)    # -> RetrievalResult (parsed query + ranked matches)
engine.related(registry_id)    # -> list[RegistryEntry], direct neighbors (both directions)
engine.rank(matches)           # -> list[RetrievalMatch], sorted
engine.explain(match)          # -> list[str], readable reason lines
```

## Test Results

- `tests/test_retrieval_engine.py`: **35 passed** — query parsing,
  primary matches (title/heading/preview, case-insensitivity, no-match),
  secondary matches (both relation directions, no double-counting when
  a match is both primary and secondary, no recursion past one hop,
  accumulation of multiple reasons for one entry), `related()`,
  ranking (weight sum, descending sort, deterministic tie-break),
  `explain()`, determinism (repeated calls, no cross-call state
  pollution), no mutation of `RepositoryIndex`/`KnowledgeRegistry`,
  edge cases (empty query, stopword-only query, no-match query, empty
  repository, single-document repository with no relations), and one
  real-repository integration test.
- Full suite: **132 passed** (97 before this milestone + 35 new), no
  regressions.

## Real-Repository Verification

Ran against the live OCOM-Reader repository (`RepositoryIndexBuilder(".").build()`
→ `RegistryBuilder().build(index)` → `RetrievalEngine(index, registry)`)
with several distinct queries before writing any test assertions:

- `"runtime"` → 15 matches, top scores 20.0 (title + 2 heading hits) for
  `MILESTONE-005.md`, `OCOM-Runtime-v0.2-Reliability-Design.md`,
  `OCOM-Runtime-v0.2-Resolution-Evidence-Design.md`.
- `"evidence"` → 20 matches, correctly separating a strong title match
  (`OCOM-Runtime-v0.2-Resolution-Evidence-Design.md`, 20.0) from
  relation-only secondary matches (e.g. `ADR-003-metadata-semantic-boundary.md`,
  13.0, five relation reasons, no text hit).
- `"identity resolution"` → 20 matches. This query is what exposed the
  outbound-only expansion bug: `MILESTONE-007-DESIGN.md` builds on
  `MILESTONE-003.md` (a primary text match) but was missing from
  results until secondary expansion was made bidirectional — confirmed
  present after the fix.
- `"xyz-nonexistent-term"` → 0 matches, as expected.
- Determinism: two `.retrieve("runtime")` calls produced identical
  `model_dump()` output; a `.retrieve("evidence")` call in between two
  `.retrieve("runtime")` calls did not change the second result
  (no cross-call state).
- Mutation: `index.model_dump()` and `registry.model_dump()` were
  identical before and after a batch of `retrieve()`/`related()` calls.

## Known Limitations / Design Decisions

- **No relevance beyond one hop.** A document connected to a primary
  match only through an intermediate document (2+ relation hops away)
  is never surfaced. This keeps results bounded and every reason
  traceable to a specific primary match, at the cost of missing more
  distant but potentially relevant documents. A future milestone could
  make hop count configurable if real usage shows this is too narrow.
- **`document_type` is not a ranking factor**, as stated above — an
  explicitly deferred, not forgotten, decision.
- **No phrase or proximity matching.** Multi-word queries are treated
  as independent tokens; a document matching only one token out of
  three scores the same per-token as a document matching all three
  under a different combination. This mirrors `QueryNormalizer`'s own
  scope (MILESTONE-005) and was not extended here.
- **Substring matching, not word-boundary matching.** A token matches
  anywhere within a field, including inside another word (e.g. `"is"`
  inside `"history"`). This was inherited from reusing `QueryNormalizer`
  tokenization together with plain substring checks against Index text,
  and was surfaced during test-writing (a test fixture's own filename
  leaked into its preview text and caused an unintended match). No
  false positive was observed against the real repository's actual
  document set, but this is a real, documented gap, not a guarantee.
- **`explain()` returns raw fact strings, not natural language.**
  Composing a human-readable sentence (matching the task's own example
  phrasing, e.g. "Связан через builds_on.") is left to M009, consistent
  with keeping this layer free of generated text.

## Proposals for M009 (Answer Composer)

- Consume `RetrievalResult` to compose natural-language answers,
  translating each `MatchReason` into the kind of human sentence this
  milestone deliberately did not generate.
- Decide, with real evidence, whether `document_type` (or some other
  grounded signal) should influence ranking — do not guess a weight.
- Consider whether multi-hop relation context (e.g. "this document is
  two steps removed from your query, via X") is worth surfacing to the
  user even though it's excluded from the match set itself.
