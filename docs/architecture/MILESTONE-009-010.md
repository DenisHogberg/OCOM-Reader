# MILESTONE-009-010: Answer Composer & Reader MVP

**Date:** 2026-07-24
**Status:** Frozen — first working OCOM Reader MVP.
**Builds on:** [MILESTONE-009-010-DESIGN.md](MILESTONE-009-010-DESIGN.md), [MILESTONE-008](MILESTONE-008.md), [MILESTONE-007](MILESTONE-007.md), [MILESTONE-006](MILESTONE-006.md)

## Objective

Compose `RetrievalResult` into a structured, human-readable answer,
and expose the full Repository → Index → Registry → Retrieval →
Composer pipeline behind a public `Reader` facade and a CLI — the
first complete, working OCOM Reader MVP: it answers questions about
this repository's own documentation with no LLM, no embeddings, and no
semantic search anywhere in the chain.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `ComposedAnswer`, `DocumentRef`, `ExplainedDocument` | `composer/models.py` | Implemented |
| `AnswerComposer` | `composer/answer_composer.py` | Implemented |
| `explain_reason`, `render` | `composer/formatter.py` | Implemented |
| `Reader` | `reader.py` | Implemented |
| CLI (`ask`/`search`/`related`/`explain`) | `cli.py`, `__main__.py` | Implemented |

Only `pyproject.toml`'s `[project.scripts]` line changed outside new
files (see below). `runtime/`, `registry/`, `indexer/`, `retrieval/`,
`core/`, `interfaces/`, `storage/`, `identity/`, `intelligence/`,
`adapters/`, `normalizers/`, `agent/`, and `main.py` are all untouched
— confirmed via `git diff --stat` (empty for every one of them).

## Naming Collision (flagged in design, confirmed at review)

`ocom_reader.agent.answer.AnswerComposer` and
`ocom_reader.composer.answer_composer.AnswerComposer` are two
unrelated components that happen to share a name — the former composes
an `Answer` from OCOM domain-object `Evidence` (M002-M005's Agent
pipeline); the latter composes a `ComposedAnswer` from a
`RetrievalResult` over this repository's own documentation (M006-M008's
pipeline). Per explicit review sign-off, neither was renamed; the rule
is simply "never mix them in the same scope unqualified." No file in
this milestone imports both.

## Architecture

```
Repository (filesystem)
        │
        ▼  RepositoryIndexBuilder (M006)
RepositoryIndex
        │
        ▼  RegistryBuilder (M007)
KnowledgeRegistry
        │
        ▼  RetrievalEngine.retrieve() (M008)
RetrievalResult
        │
        ▼  AnswerComposer.compose() (M009-010)
ComposedAnswer
        │
        ▼  formatter.render() (M009-010)
Plain-text answer
        │
        ▼  Reader.answer() / CLI `ask`
User
```

`Reader` owns exactly one instance of each of the four pipeline
components, built once at construction, and every public method is a
direct delegation — no new matching, ranking, or composition logic
lives in `reader.py` itself.

## Answer Composer

`AnswerComposer(index: RepositoryIndex, registry: KnowledgeRegistry).compose(result: RetrievalResult) -> ComposedAnswer`

**Never decides anything** — the invariant added at design review:
Composer does not rank, search, or filter by relevance. Concretely:

- **Grouping into `evidence` vs `related_documents`** is a
  reclassification of a fact `RetrievalEngine` already computed: a
  match with any `title_match`/`heading_match`/`preview_match` reason
  is evidence; a match with only relation-kind reasons is related. No
  new relevance judgment is made.
- **Order within each group** is exactly `RetrievalResult.matches`'
  order — untouched, never re-sorted.
- **`reading_order`** is a deterministic topological sort
  (Kahn's algorithm, ties broken by `registry_id`) of `builds_on` /
  `architecture_sequence` edges that already exist between documents
  already in the result set. It can reorder documents already present;
  it never adds or removes one. If the result set has zero such edges
  among its own members, `reading_order = []` ("not applicable"). If a
  cycle were ever detected, the same empty result is returned rather
  than risk misrepresenting the data — not observed on real data, but
  handled defensively.
- **Deduplication** of an exact-duplicate `registry_id` (same document
  appearing twice in the input) is the one defensive step that could
  be mistaken for filtering — it isn't: it merges reasons for the
  *same* document, never drops a distinct one. `RetrievalResult` is
  already duplicate-free per M008's own tests, so this path is
  expected to be dead code in practice against `Reader`-produced
  input; it exists because `AnswerComposer.compose()` is public API,
  callable with any `RetrievalResult` a caller constructs.

`RepositoryIndex` and `KnowledgeRegistry` are held read-only, solely to
resolve pointers at presentation time: `document_id -> title/path`
(`RegistryEntry` itself carries no title, by M007's own structural
invariant) and existing relation edges for `reading_order`. Composer
never calls `RetrievalEngine.search()`/`.retrieve()`.

## Answer Format

Every `ComposedAnswer` always has the same four-section shape, per
review — a section is never omitted, only marked empty:

```
Question: <query>

Answer
  <templated summary — count + top title, or "No documentation found">

Evidence
  <found documents, or "(none)">

Related Documents
  <related documents, or "(none)">

Recommended Reading Order
  <topological order, or "(not applicable)">
```

`answer` and `evidence` (as field names) were chosen over the design
doc's original `summary`/`found_documents` to mirror this four-section
structure 1:1. "Evidence" here is reused in its ordinary English sense
("documents supporting this answer") — unrelated to
`core.Evidence`/`agent.evidence.Evidence`.

Reason text comes from a fixed kind → template lookup table in
`formatter.py` (`explain_reason`), the same "dictionary, not
generation" discipline `ranking.py`'s `SCORE_WEIGHTS` already uses —
e.g. `"Title match: identity"`, `"Related via builds_on to docs/architecture/MILESTONE-003.md"`.
No prose is generated anywhere in this milestone; every word in a
`ComposedAnswer` traces back to already-known Index/Registry/Retrieval
data.

**Output language:** English, for consistency with every other
user-facing string in this codebase (`NOT_GROUNDED_TEXT`,
`AMBIGUOUS_TEXT`, all prior milestone docs) — flagged in the design
doc, no objection raised at review.

## Reader Public API

```python
reader = Reader(repository_root)
reader.answer(query)          # -> ComposedAnswer
reader.search(query)          # -> list[RetrievalMatch], ranked
reader.related(registry_id)   # -> list[RegistryEntry], direct neighbors
reader.explain(query)         # -> list[ExplainedDocument], evidence + related, with reasons
```

`Reader` builds `RepositoryIndex`/`KnowledgeRegistry`/`RetrievalEngine`/`AnswerComposer`
once at construction (mirroring the "build once, query many times, no
incremental mutation" pattern already used throughout M006-M008) and
is otherwise stateless — re-verified at this layer with the same
before/after `model_dump()` checks used in every prior milestone.

## CLI

Single binary, subcommands, per review (no second console script):

```bash
ocom-reader ask "identity resolution"
ocom-reader search "registry"
ocom-reader related docs/architecture/MILESTONE-003.md
ocom-reader explain "identity resolution"

python -m ocom_reader ask "runtime"   # equivalent, no install required
```

`pyproject.toml`'s existing `ocom-reader` console script now points to
`ocom_reader.cli:main` instead of `ocom_reader.main:main`. Phase 1's
original smoke-test entry point (`main.py`) is unchanged and still
directly runnable (`python -m ocom_reader.main` or by import) — it is
simply no longer the default console-script target, since this
milestone's own task was to build the CLI that target should point to.

`search` and `related` print raw `registry_id`s (`RetrievalMatch`/`RegistryEntry`
are pointer-only, same as M007/M008 — no title is resolved for them).
`ask` and `explain` go through `AnswerComposer`, the only place in
this pipeline that resolves titles for presentation, so their output
is more readable. This asymmetry is deliberate: it reflects exactly
which layer owns title resolution, not an inconsistency to fix later.

## Test Results

- `tests/test_answer_composer.py`: **20 passed** — grouping (evidence
  vs. related, mixed-reason classification), order preservation (no
  re-ranking), title/path resolution, answer text templating, reading
  order (`builds_on`, `architecture_sequence`, `references` excluded,
  restricted to the result set, empty when no ordering edges exist),
  defensive dedup, the "never drops a document" invariant, no
  mutation of inputs, determinism, and formatter output shape.
- `tests/test_reader_pipeline.py`: **12 passed** — full pipeline
  correctness on synthetic repositories, all four `Reader` methods,
  determinism, cross-call isolation, edge cases (empty repository,
  unknown `registry_id`), and real-repository integration
  (12 distinct queries, determinism, a known-relevant match, and a
  full-session no-side-effects check).
- `tests/test_cli.py`: **11 passed** — all four subcommands (success
  and no-match paths), default `--repo`, missing/unknown subcommand
  rejection, and one subprocess smoke test of the actual installed
  console entry point against the real repository.
- Full suite: **175 passed** (132 before this milestone + 43 new), no
  regressions.

## Real-Repository Verification

Ran `Reader` against the live OCOM-Reader repository with 12 distinct
queries before writing any test assertions (`identity resolution`,
`runtime`, `evidence`, `registry`, `retrieval`, `classification`, `how
does runtime work`, `knowledge registry architecture`, `repository
indexer`, `answer composer`, `metadata namespace`,
`zzznonexistenttermxyz`):

- All 12 queries produced deterministic `ComposedAnswer.model_dump()`
  output across repeated calls.
- `grounded` correctly tracked "at least one evidence document" for
  every query, including the one deliberately-unmatched query (0
  evidence, `grounded=False`).
- No cross-call state pollution: interleaving `reader.answer("evidence")`
  and `reader.answer("registry")` between two `reader.answer("runtime")`
  calls left the second result identical to the first.
- No mutation of `RepositoryIndex` or `KnowledgeRegistry` across a full
  session of `answer()`/`search()`/`explain()`/`related()` calls
  (`model_dump()` equality before/after).
- Both CLI invocation forms (`python -m ocom_reader` and the installed
  `ocom-reader` console script) were run manually against all four
  subcommands and produced correct, readable output — see the
  transcript captured during implementation.

## Known Limitations

- **`reading_order` is one hop deep**, inherited directly from M008's
  own one-hop secondary-match boundary — it orders exactly the
  documents Retrieval already surfaced, not a general curriculum.
- **No ranking weight for `document_type`**, inherited from M008 — an
  explicitly deferred decision, not an oversight.
- **`search`/`related` output pointers, not titles.** This is a
  deliberate layering choice (see CLI section above), not a missing
  feature — resolving titles outside `AnswerComposer` would duplicate
  the one place this pipeline does that resolution.
- **`answer` text is intentionally terse** — count and top title only,
  never a content summary. Consistent with "no new knowledge
  generated" holding all the way to the CLI.
- **Composer's defensive dedup path is untested-by-necessity dead
  code** against real `Reader` usage (RetrievalResult is already
  duplicate-free); it is tested directly in
  `test_answer_composer.py` by constructing a malformed
  `RetrievalResult` by hand, since `AnswerComposer.compose()` is
  public API independent of `Reader`.

## OCOM Reader Roadmap

```
✅ M001 Runtime Foundation
✅ M002 Search Engine
✅ M003 Identity & Resolution
✅ M004 Evidence Layer
✅ M005 Runtime v0.2 Stabilization
✅ M006 Repository Indexer
✅ M007 Knowledge Registry
✅ M008 Retrieval Engine
✅ M009-010 Answer Composer & Reader MVP

🏁 First complete OCOM Reader MVP
```

## Directions Beyond the MVP

- Multi-hop reading order / relevance, if real usage shows the current
  one-hop boundary too narrow.
- A grounded `document_type` ranking weight, once real evidence exists
  to justify specific numbers.
- Phrase/proximity-aware search, beyond today's independent-token
  matching (a gap inherited unchanged from M008).
- Optionally surfacing titles for `search`/`related` CLI output,
  should that prove more useful in practice than the current
  pointer-only view.
