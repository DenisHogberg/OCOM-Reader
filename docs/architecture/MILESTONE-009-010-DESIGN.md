# MILESTONE-009-010: Answer Composer & Reader MVP — Design

**Date:** 2026-07-24
**Status:** Design proposal — no code yet, awaiting sign-off.
**Builds on:** [MILESTONE-008](MILESTONE-008.md) (Retrieval Engine), [MILESTONE-007](MILESTONE-007.md) (Knowledge Registry), [MILESTONE-006](MILESTONE-006.md) (Repository Indexer)

## Objective

Compose `RetrievalResult` into a structured, human-readable answer,
and expose the whole Repository → Index → Registry → Retrieval →
Answer pipeline behind one small public `Reader` facade and a minimal
CLI. No new knowledge is generated anywhere in this layer — every word
in a composed answer traces back to data already present in
`RepositoryIndex` or `KnowledgeRegistry`.

## Naming collision to flag up front

`ocom_reader.agent.answer.AnswerComposer` **already exists** — it
composes an `Answer` from `UnifiedEvidenceContext` (OCOM domain-object
Evidence, from the M002-M005 Agent/Identity/Runtime pipeline, wired
into `RuntimeContext.answer_composer`). That pipeline answers questions
about **OCOM domain objects** extracted from documentation.

This milestone's Composer is a **different, unrelated component**: it
answers questions about **this repository's own documentation
structure** (which Markdown files exist and how they relate — M006/M007/M008's
subject matter). Same class name, same task vocabulary, two
independent pipelines that happen to share no code path.

To avoid confusion in imports and in future milestone docs:
- New model is called `ComposedAnswer`, not `Answer` (avoids colliding with `agent.answer.Answer`).
- New composer class is `AnswerComposer` as the task requests, but it lives at `ocom_reader.composer.answer_composer.AnswerComposer` — always import qualified or aliased (`from ocom_reader.composer import AnswerComposer as DocsAnswerComposer` where both are used together) to prevent silent shadowing.
- `MILESTONE-009-010.md` (final doc) will state this explicitly again.

## Package Structure

```
src/ocom_reader/
    composer/
        __init__.py
        models.py            # ComposedAnswer, DocumentRef, ExplainedDocument
        answer_composer.py   # AnswerComposer — RetrievalResult -> ComposedAnswer
        formatter.py         # ComposedAnswer -> plain-text rendering (CLI output)
    reader.py                 # Reader — public facade over the whole pipeline
    cli.py                     # argparse-based CLI, thin wrapper over Reader
    __main__.py                # enables `python -m ocom_reader ask "..."`
```

`reader.py` and `cli.py` sit outside `composer/` because they are pipeline
glue (same role `runtime/pipeline.py` and `runtime/scenario.py` play for
the Agent pipeline), not part of the Composer's own responsibility.
`composer/` stays focused on exactly one job: turning a `RetrievalResult`
into a `ComposedAnswer`.

`main.py` (the existing `ocom-reader` console script, Phase 1's
storage/config smoke test) is untouched — it is a different, older
entry point and out of this milestone's scope.

## Composer Architecture

### Why Composer needs read-only access to `RepositoryIndex` and `KnowledgeRegistry`

`RetrievalMatch.entry` is a `RegistryEntry` — structurally just
`(registry_id, document_id, entry_type)`, no title, no path (M007's
"pointer, not copy" invariant, enforced by a structural test). A
human-readable answer needs titles. Rather than have `RetrievalEngine`
start copying title text into `RetrievalMatch` (which would break that
invariant one layer earlier), `AnswerComposer` resolves
`document_id -> title/path` itself, at presentation time, by reading
`RepositoryIndex` directly — the same "resolve pointers at the edge"
discipline `EvidencePresentationMapper` already established in M005.

`KnowledgeRegistry` read access is needed for exactly one thing:
computing a reading order from `builds_on` / `architecture_sequence`
relations restricted to the matched document set (see below). This is
a lookup (`registry.related(id, type)`), not a search — Composer never
calls `RetrievalEngine.search()`/`.retrieve()` itself, and never
constructs new relations.

Both references are stored read-only and never mutated — verified the
same way M008 verified `RetrievalEngine` (before/after `model_dump()`
equality on `RetrievalResult`, `RepositoryIndex`, `KnowledgeRegistry`).

```python
class AnswerComposer:
    def __init__(self, index: RepositoryIndex, registry: KnowledgeRegistry) -> None: ...
    def compose(self, result: RetrievalResult) -> ComposedAnswer: ...
```

### Algorithm

1. **Classify each `RetrievalMatch`** as *found* (primary — has at
   least one `title_match`/`heading_match`/`preview_match` reason) or
   *related* (secondary — only relation-kind reasons). `RetrievalResult`
   already keeps these as one flat, ranked list; Composer splits them
   back into the two groups the task's answer format requires. No
   document can be in both groups — this mirrors the invariant M008's
   own tests already proved (`_secondary_matches` never re-adds a
   primary match).

2. **Resolve each match into an `ExplainedDocument`**: look up its
   `DocumentIndexEntry` in `RepositoryIndex` for `title`/`path`/`document_type`,
   and render its `reasons` into human-readable lines via
   `formatter.explain_reason(reason) -> str` (a fixed kind→template
   lookup table — `title_match` → `"Title match: {detail}"`,
   `builds_on` → `"Related via builds_on to {detail}"`, etc. — the same
   "fixed table, not generation" discipline `ranking.py` already uses
   for scores). This is new work M008 explicitly deferred to this
   milestone.

3. **Deduplicate** (defensive, not load-bearing): if the same
   `registry_id` somehow appeared twice in `RetrievalResult.matches`
   (shouldn't happen per M008's own invariants, but Composer must not
   silently produce a broken answer if it ever did), keep only the
   first (highest-ranked) occurrence and merge its reasons.

4. **Compute `summary`** — a fixed template, not generated prose:
   - No matches: `No documentation found for "{query}".`
   - Otherwise: `Found {N} relevant document(s) for "{query}". Most relevant: "{top_title}".`

5. **Compute `reading_order`** (only "if applicable" — per the task):
   - Take the registry_ids of all found + related documents (set `R`).
   - Build directed edges *restricted to `R`*: for `builds_on`, edge
     `base -> dependent` (read the base first); for `architecture_sequence`,
     edge `earlier -> later`, both read straight from `KnowledgeRegistry.relations`.
   - Topologically sort (Kahn's algorithm), breaking ties by `registry_id`
     for determinism.
   - If `R` has zero such edges among its own members, `reading_order = []`
     ("not applicable" — the task's own escape hatch). If a cycle is
     detected (not expected — M007 already guarantees no self-loops,
     and no cross-relation cycle has been observed on the real
     repository — but not something to crash on), also return `[]`
     rather than an order that would misrepresent the data.

6. **Assemble `ComposedAnswer`** — see model below. `grounded = bool(found_documents)`.

Composer never calls anything on `RetrievalEngine`, never re-ranks
(the order `RetrievalResult.matches` already provides via `Ranker` is
preserved as-is within each group), and never mutates its inputs.

## Data Models (`composer/models.py`)

```python
class DocumentRef(BaseModel):
    registry_id: str
    document_id: str
    title: str
    path: str
    document_type: str

class ExplainedDocument(BaseModel):
    document: DocumentRef
    reasons: list[str]      # human-readable lines, e.g. "Title match: identity"
    score: float

class ComposedAnswer(BaseModel):
    query: str
    summary: str
    found_documents: list[ExplainedDocument]
    related_documents: list[ExplainedDocument]
    reading_order: list[DocumentRef]
    grounded: bool
```

## `formatter.py`

One function, `render(answer: ComposedAnswer) -> str`, producing the
plain-text block the task's example lays out:

```
Question: <query>

Summary
  <summary>

Found Documents
  - <title> (<path>) — score <score>

Related Documents
  - <title> (<path>) — score <score>

Why These Were Included
  - <title>: <reason line>, <reason line>, ...

Recommended Reading Order
  1. <title>
  2. <title>
  (omitted entirely if reading_order is empty)
```

**Language note:** the task's own example uses Russian section labels
("Краткий ответ", "Связанные документы", ...) as illustrative
structure. Every other user-facing string in this codebase so far
(`NOT_GROUNDED_TEXT`, `AMBIGUOUS_TEXT`, milestone docs, CLI output) is
English. Proposal: keep `formatter.py` output in English for
consistency with the rest of the project, matching the section names
above 1:1 in meaning. Flagging this explicitly — say so now if Russian
output is actually wanted; otherwise implementation proceeds in
English.

## Reader Public API (`reader.py`)

```python
class Reader:
    def __init__(self, repository_root: Path) -> None:
        self._index = RepositoryIndexBuilder(repository_root).build()
        self._registry = RegistryBuilder().build(self._index)
        self._engine = RetrievalEngine(self._index, self._registry)
        self._composer = AnswerComposer(self._index, self._registry)

    def answer(self, query: str) -> ComposedAnswer: ...
    def search(self, query: str) -> list[RetrievalMatch]: ...          # raw, unranked matches
    def related(self, registry_id: str) -> list[RegistryEntry]: ...    # direct neighbors
    def explain(self, query: str) -> list[ExplainedDocument]: ...      # found+related with reasons, no summary/reading order
```

`Reader` builds the Index/Registry once at construction (mirrors
`RegistryBuilder`/`RetrievalEngine`'s own "build once, query many
times, no incremental mutation" pattern already used throughout
M006-M008) and is otherwise stateless across calls — same determinism
and no-shared-mutable-state guarantees as `RetrievalEngine`, re-verified
at this layer too.

## CLI (`cli.py`, `__main__.py`)

```
python -m ocom_reader ask "identity resolution"
```

`cli.py` exposes `main(argv: list[str] | None = None) -> int` (argparse,
one subcommand for now: `ask <query> [--repo PATH]`, default `--repo .`),
prints `formatter.render(reader.answer(query))` to stdout, returns 0.
`__main__.py` is a two-line `sys.exit(main())`.

**Console-script entry point:** the task shows `ocom-reader ask "..."`
as an alternative form. The existing `ocom-reader` script
(`pyproject.toml` → `ocom_reader.main:main`) is Phase 1's own smoke
test entry point and is out of scope to repurpose or branch inside.
Proposal: add a **new**, separate console script,
`ocom-reader-ask = "ocom_reader.cli:main"`, so both invocation forms
from the task work without touching `main.py`. `python -m ocom_reader`
remains the primary documented form.

## End-to-End Pipeline

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
        ▼  AnswerComposer.compose() (M009-010, new)
ComposedAnswer
        │
        ▼  formatter.render() (M009-010, new)
Plain-text answer → user (CLI / Reader.answer())
```

`Reader` owns exactly one instance of each of the four components and
wires them in this order; no component reaches around another (Composer
never talks to `RetrievalEngine`, CLI never talks to `RetrievalEngine`
or `RegistryBuilder` directly — only to `Reader`).

## Invariants Carried Forward

- Deterministic: same query + same repository state → byte-identical `ComposedAnswer` (`model_dump()` equality), verified via repeated calls, same discipline as M008.
- No state between requests: `Reader`/`AnswerComposer` hold only their read-only collaborators, never per-call mutable state.
- No LLM, no embeddings, no semantic search anywhere in `composer/`, `reader.py`, or `cli.py`.
- `RepositoryIndex`, `KnowledgeRegistry`, and `RetrievalResult` are never mutated by Composer, Reader, or CLI — verified by `model_dump()` before/after, same as every prior milestone.
- `composer/` and `reader.py` are the only new production code; `retrieval/`, `registry/`, `indexer/`, `runtime/`, `agent/`, `identity/`, `intelligence/`, `core/`, `interfaces/`, `storage/`, `adapters/`, `normalizers/` stay untouched — confirmed via `git diff --stat` before the final report, same as every prior milestone.

## Known Scope Limits (stated up front, not discovered later)

- `reading_order` only ever reflects `builds_on`/`architecture_sequence` edges already present among the matched+related document set — it is not a general "recommended curriculum," just a topological ordering of what the query already surfaced.
- `summary` is intentionally terse and template-based; it does not attempt to summarize document *content*, only counts and the top title — consistent with "no new knowledge generated."
- Composer's dedup step (step 3 above) is defensive; `RetrievalResult` should already be duplicate-free per M008's own tests, so this path is expected to be untested-by-necessity dead code in practice but kept because Composer must not assume its input is always well-formed from a caller Reader doesn't control (`AnswerComposer.compose()` is public API, callable directly).

## Open Question for Sign-Off

Everything above is a concrete proposal, not a question — except the
one language flag (English vs. Russian formatter output) called out
above. Proceeding with English unless told otherwise.
