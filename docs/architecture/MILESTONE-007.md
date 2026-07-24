# MILESTONE-007: Knowledge Registry v0.1

**Date:** 2026-07-23
**Status:** Frozen — first working Knowledge Registry, built strictly on [MILESTONE-007-DESIGN.md](MILESTONE-007-DESIGN.md).
**Builds on:** [MILESTONE-007-DESIGN.md](MILESTONE-007-DESIGN.md), [MILESTONE-006](MILESTONE-006.md) (Repository Indexer)

## Objective

Implement the first working Knowledge Registry: a structured,
deterministic representation of the named things this repository's
documentation contains (currently: one entry per indexed document) and
how they relate — built entirely from `RepositoryIndex` (M006), with
no LLM, no embeddings, no fuzzy matching, and no content duplication.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `RegistryEntry` | `registry/models.py` | Implemented |
| `KnowledgeRelation` | `registry/relations.py` | Implemented |
| `KnowledgeRegistry` (container + API) | `registry/registry.py` | Implemented |
| `RegistryBuilder` | `registry/registry_builder.py` | Implemented |
| `builds_on_links` extraction (indexer extension) | `indexer/markdown_parser.py`, `indexer/models.py`, `indexer/index_builder.py` | Implemented — justified change, see below |

## Architecture

```
RepositoryIndex (M006, read-only)
        │
        ▼
RegistryBuilder.build(index) -> KnowledgeRegistry
        │
        ├── one RegistryEntry per DocumentIndexEntry (1:1, pointer-only)
        ├── "builds_on"   relations, from DocumentIndexEntry.builds_on_links
        ├── "references"  relations, from DocumentIndexEntry.internal_links
        │                 (minus pairs already claimed by "builds_on")
        └── "architecture_sequence" relations, from consecutive
            numbered document ids within the same series (ADR-*, MILESTONE-*)
        ▼
KnowledgeRegistry — lookup() / get() / contains() / neighbors() / related()
```

Every relation type has exactly one, unambiguous, mechanical detection
rule — no type was added speculatively (per
[MILESTONE-007-DESIGN.md](MILESTONE-007-DESIGN.md)'s own caution).

## Interface Deviations from MILESTONE-007-DESIGN.md

The design document's own data model was explicitly illustrative
("do not assume these names are final"). This implementation task's
invariants were stricter on one specific point, and the stricter
reading was followed:

- **`RegistryEntry` has no `name` field.** The design doc's sketch
  included `name: str` ("the document's title, verbatim"). This
  task's own invariant list explicitly forbids "копировать заголовки
  документов" / "дублировать метаданные Index" — a title is Index
  metadata. Rather than treat these as compatible, the stricter
  reading was applied: `RegistryEntry` carries only `registry_id`,
  `document_id`, `entry_type`. Anything about a document's content —
  including its title — must be looked up through `document_id` via
  `RepositoryIndex.get()`. This is enforced by a structural test
  (`test_registry_entry_has_no_content_bearing_field`), not just
  stated in prose.
- **`aliases` was dropped entirely.** The design doc named it as a
  future affordance for known alternate names; nothing in v0.1
  populates it (no alias detection was ever in scope), so an unused
  field was not added speculatively — consistent with this project's
  standing discipline against building for a need that doesn't exist
  yet.
- **`lookup()` and `get()` are the same operation.** The task's own
  API example listed both without distinguishing behavior; rather than
  invent a difference that wasn't asked for, `get()` is a documented
  one-line alias of `lookup()`.

## Justified Change: `indexer/` (`builds_on_links`)

**What changed:** `MarkdownParser.parse()` now also extracts links
found specifically on a document's own `**Builds on:**` header line
(`ParsedMarkdown.builds_on_links`); `DocumentIndexEntry` gained a
`builds_on_links: list[str]` field, populated by
`RepositoryIndexBuilder` the same way `internal_links` already is.

**Why this was judged necessary, not optional:** the acceptance
criteria for this milestone require "Repository Index остаётся
единственным источником данных" (Repository Index remains the sole
source of data). Detecting a `builds_on` relation requires knowing
*which* links came from the `**Builds on:**` line specifically — a
distinction `RepositoryIndex` did not previously expose
(`internal_links` mixes every link in a document together). Two
alternatives were rejected:

1. **Registry re-reads and re-parses the raw file itself**, to find
   the `**Builds on:**` line independently. Rejected: this would make
   `Storage`/filesystem a second data source alongside the Index,
   directly contradicting "Index remains the sole source," and would
   duplicate `MarkdownParser`'s existing responsibility inside a
   different package (Modeling Rule 8).
2. **Skip `builds_on` detection entirely in v0.1**, only ever producing
   generic `"references"` relations. Rejected: the task explicitly asks
   for `builds_on` as a named, required relation type with "достаточные
   основания" (sufficient grounding) — and the grounding exists,
   confirmed directly (`grep -c "Builds on:"` across
   `docs/architecture/*.md` returned exactly one match in all 16
   documents checked during M007's design phase).

The change made is small (one new regex, one new field, reuse of
existing link-resolution logic) and strictly additive — no existing
field's meaning changed, confirmed by the full pre-existing
`test_repository_indexer.py` suite passing unmodified, plus two new
tests covering the addition specifically.

## Invariants

Each required invariant is backed by a specific, named test, not just
documented:

| Invariant | Enforced by |
|---|---|
| Registry stores no document text | `test_registry_entry_has_no_content_bearing_field` — asserts `RegistryEntry`'s field set is exactly `{registry_id, document_id, entry_type}` |
| Registry never modifies `RepositoryIndex` | `test_registry_never_mutates_the_repository_index` — snapshot before/after `build()`, compared |
| Every `RegistryEntry` points to an existing `IndexEntry` | `test_every_registry_entry_points_to_an_existing_index_entry` |
| No cyclic (self-referential) relations | `test_no_self_referential_relations` — plus structurally prevented in `RegistryBuilder` itself (`target_id != document.id` checks in both `_builds_on_relations` and `_reference_relations`) |
| Registry is fully reproducible | `test_registry_build_is_deterministic` (same `RepositoryIndex` object) and `test_registry_is_reproducible_across_independent_index_builds` (two independently-built indexes of the same files) |

**On "no cyclic references," precisely:** this was interpreted as "no
relation whose source and target are the same entry" — a concrete,
testable, structurally-preventable invariant — not general
graph-cycle detection across multi-hop paths (e.g. A→B→C→A). Real
documents in this repository do legitimately reference each other in
both directions (ADR-003 and ADR-005 both link to each other, for
instance), and that is correct, expected behavior for a `references`
relation, not a violation to detect and reject. Building a
transitive-cycle detector was judged out of scope — it would add
machinery this task's invariants do not actually require and edges
toward graph algorithms the design doc's own §Risks section warns
against over-building.

## Interaction with Repository Index

Strictly one-directional and read-only: `RegistryBuilder.build(index)`
takes a `RepositoryIndex` and only ever calls read methods on it
(`.entries`, field access) — never `RepositoryIndex`'s own mutation
paths (it has none exposed either; `RepositoryIndexBuilder.build()` is
the only thing that constructs one). No component under `indexer/`
was changed to depend on `registry/` in return — confirmed by
`indexer/` having zero imports from `registry/` anywhere.

## Guarantees

- **Deterministic and reproducible**, confirmed against both synthetic
  fixtures and the real repository: two builds from the same `Index`
  produce byte-identical `model_dump()` output, and two independent
  `RepositoryIndexBuilder` runs feeding two `RegistryBuilder` runs also
  agree.
- **No semantic interpretation anywhere.** Every relation-detection
  rule is a fixed pattern match (a specific header line, a filename
  number sequence) — the same "dictionary, not inference" discipline
  already used by `intelligence/classification.py`.
- **No duplication of Repository Index data** — verified structurally,
  not just by convention.
- **No regressions.** All 74 pre-existing tests (72 before this
  milestone, +2 for the justified `indexer/` extension) pass
  unmodified; 23 new tests were added for the Registry itself. 97
  passed, 0 failed, run against this repository for real, not assumed.

## Known Limitations

- **Only `Document`-level entries exist.** `Concept`/`Component`/
  `Specification` remain valid `entry_type` values in principle, but
  nothing in this milestone populates them — exactly the boundary
  [MILESTONE-007-DESIGN.md](MILESTONE-007-DESIGN.md) drew and this
  implementation did not cross.
- **`references` relations are still directional and un-weighted** —
  no notion of "this reference matters more than that one." Left for
  a future Retrieval Engine, per the design doc's own component
  boundary.
- **`architecture_sequence` only recognizes `ADR-` and `MILESTONE-`
  filename prefixes** — a repository organized differently would need
  this pattern revisited, the same caveat already named in
  [MILESTONE-006](MILESTONE-006.md#known-limitations) for
  `document_type` classification.
- **No incremental rebuild** — inherited from `RepositoryIndex`
  itself; `RegistryBuilder.build()` always processes the whole index
  from scratch.

## Test Results

```
tests/test_repository_indexer.py    12 passed  (10 existing + 2 new, for builds_on_links)
tests/test_knowledge_registry.py    23 passed  (new)
full suite                          97 passed, 0 failed
```

Pre-commit checks performed, in order:

1. `RegistryBuilder` run against the real `OCOM-Reader` repository:
   22 documents indexed, 119 relations (56 `builds_on`, 52
   `references`, 11 `architecture_sequence`), 0 self-referential
   relations.
2. Determinism confirmed by two consecutive builds against the real
   repository, compared by full `model_dump()` equality: identical.
3. `git diff --stat` confirmed empty for `runtime/`, `adapters/`,
   `intelligence/`, `identity/`, `storage/`, `core/` — no
   architectural violations. `indexer/`'s change is the one documented,
   justified exception (see above).

## Next Milestone Proposal

A **Retrieval Engine** that answers a query by finding and ranking
relevant `RegistryEntry` nodes — the component `KnowledgeRegistry`
was deliberately built without (per its own §Registry Responsibilities:
no search, no ranking). This is the natural next consumer named in
[MILESTONE-007-DESIGN.md](MILESTONE-007-DESIGN.md)'s own Component
Boundaries diagram, and the first place this milestone's open question
about converging with (or staying separate from) the existing
`agent/answer.py` OCOM object-reasoning track would need an answer.
