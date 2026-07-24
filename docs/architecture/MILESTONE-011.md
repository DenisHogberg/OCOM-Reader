# MILESTONE-011: Repository Loader

**Date:** 2026-07-24
**Status:** Frozen — Repository Loader implemented, verified against three real repositories, not yet wired into `Reader`.
**Builds on:** [MILESTONE-009-010](MILESTONE-009-010.md), [MILESTONE-006](MILESTONE-006.md)

## Objective

Give the pipeline a way to reopen a previously built index, detect
what changed since then, and recognize an incompatible stored format —
the primitives a Reader that works against *arbitrary* repositories
(not just its own) needs. Part of the "Repository Independence &
Retrieval Evolution" group (M011-014); this document covers M011 only.

## Scope Decision: M011/M012 Boundary

The task listed "reopening an existing index" under M011 and a full
"Persistent Storage" milestone (Index + KnowledgeRegistry + Retrieval
metadata + format version + repository metadata, with migration) as
M012. Building real reopen/incremental-update/compatibility-check
requires *some* persistence to reopen from, so the two overlap by
necessity. Resolution, decided before writing any code:

- **M011** owns the Index-loading *policy* (`RepositoryLoader`) and a
  deliberately minimal, single-artifact `JSONIndexStore` — just enough
  to prove reopen/incremental-update/compat-check work end to end.
  `JSONIndexStore` knows nothing about `KnowledgeRegistry` or
  Retrieval metadata.
- **M012** owns the *real* persistence design: all three artifacts
  together, real format migration, and wiring persistence into
  `Reader`'s default construction path.
- **`Reader`/`cli.py` are untouched by M011** — confirmed by
  `git diff --stat` (empty). Every existing CLI invocation
  (`ask`/`search`/`related`/`explain`) behaves exactly as before;
  `RepositoryLoader` is a new, standalone capability, not yet consumed
  by the shipped Reader MVP. This keeps M011 exactly as risky as a
  brand-new package and no riskier — no chance of an untested caching
  behavior silently changing the already-shipped CLI's side-effect
  profile (previously 100% read-only).

## Implemented Components

| Component | File | Status |
|---|---|---|
| `ChangeSet`, `FormatCompatibility` | `loader/models.py` | Implemented |
| `JSONIndexStore`, `FORMAT_VERSION` | `loader/index_store.py` | Implemented |
| `RepositoryLoader` | `loader/repository_loader.py` | Implemented |

No changes to `runtime/`, `registry/`, `indexer/`, `retrieval/`,
`composer/`, `reader.py`, `cli.py`, `core/`, `interfaces/`, `storage/`,
`identity/`, `intelligence/`, `adapters/`, `normalizers/`, `agent/`, or
`main.py` — confirmed via `git diff --stat` (empty for all of them).

## Architecture

```
repository_root (any local directory)
        │
        ▼  RepositoryLoader.load()
   previous index? ──no──► RepositoryIndexBuilder(repository_root).build() ──► save ──► return
        │yes
        ▼
   fresh = RepositoryIndexBuilder(repository_root).build()
        │
        ▼  detect_changes(previous, fresh)
   changed? ──no──► return previous (no write)
        │yes
        ▼
   save(fresh) ──► return fresh
```

`RepositoryLoader` depends only on `indexer/` (`RepositoryIndexBuilder`,
`RepositoryIndex`) and its own `loader/` siblings — it does not import
`registry/`, `retrieval/`, or `composer/` at all.

## "Correctness-First" Incremental, Not "Performance-First"

`load()` always runs a full `RepositoryIndexBuilder` scan — unchanged,
zero risk to `indexer/`. "Incremental" here means: *detect* exactly
what changed (`added`/`modified`/`removed`, by comparing
`DocumentIndexEntry.content_hash` — an already-stable M006 field, no
new hashing scheme) and *skip the write* when nothing did. It does
**not** skip re-parsing individual unchanged files during the scan
itself — that would require restructuring `RepositoryIndexBuilder` to
accept and reuse a previous index's entries, an unvalidated
performance optimization with no evidence yet that it's needed. Named
explicitly as future work (see Known Limitations), the same restraint
already applied to M008's one-hop relation expansion and M009-010's
undecided `document_type` ranking weight.

## Format Compatibility

`JSONIndexStore` writes a small envelope, not a bare `RepositoryIndex`
dump:

```json
{"format_version": "1.0", "repository_root": "...", "index": {...}}
```

`format_version` lives in the envelope, not in `RepositoryIndex`
itself — keeping `indexer/` completely untouched (no "justified
exception" needed here, unlike M007's `builds_on_links` addition).
`check_compatibility()` reports `compatible=False` whenever nothing is
stored yet, or the stored version doesn't match `FORMAT_VERSION`.
`load()` treats an incompatible or corrupted cache as if nothing were
stored — falls back to a full rebuild rather than raising — the same
"refuse to guess, fall back to a known-safe path" discipline used
throughout this project (verified by
`test_load_recovers_from_an_incompatible_cache_instead_of_failing`).

## Cache Location

Always separate from the indexed repository — `JSONIndexStore` never
writes inside `repository_root`. Default location is
`~/.ocom_reader_cache/`, keyed by a hash of the repository's resolved
absolute path (so unrelated repositories never collide). This was a
deliberate choice: `RepositoryLoader` is not wired into `Reader` yet,
so this default is only ever exercised by a caller who explicitly
constructs and uses `RepositoryLoader` — no existing code path gains a
new, surprising disk-write side effect from this milestone.

## Test Results

- `tests/test_repository_loader.py`: **18 passed** — first load /
  reopen, no-change stability, real-change detection (added/modified/removed),
  format compatibility (missing, valid, stale, corrupted-cache
  recovery), store round-trip, cache isolation from the indexed
  repository, independent cache entries for different repositories,
  empty-repository and determinism edge cases, and real-repository
  integration (load/reopen/detect_changes/compatibility against this
  project's own repository, plus a no-write-to-the-real-repository
  check).
- Full suite: **193 passed** (175 before this milestone + 18 new), no
  regressions.

## Real-Repository Verification (Three Repositories)

Run manually, before writing any test assertions, against three
structurally different real repositories on disk:

| Repository | Documents | Structure |
|---|---|---|
| `OCOM-Reader` (this project) | 26 | `docs/architecture/`, ADR-*/MILESTONE-* naming, "Builds on:" headers |
| `/Users/mac/Downloads/OCOM` | 366 | Large, `README`/`CHANGELOG`/`ROADMAP`/`CONTRIBUTING` at root plus a nested `docs/` tree, no ADR/MILESTONE convention |
| `/Users/mac/OCOM.wiki` | 7 | Small, flat wiki (`Home.md`, `Architecture.md`, ...), no subdirectories |

For each: `load()` (first run, no cache) → `reopen()` (must match) →
`load()` again with nothing changed (`detect_changes` reports zero
changes) → `check_compatibility()` (`True`). All three passed
identically. Real change detection (edit one file, add one, delete
one) was additionally verified against a scratch copy of the wiki
repository, never against the original — `git status --short` on both
external repositories was confirmed empty (nothing written to either)
both before and after every run.

The committed test suite's own real-repository test uses only this
project's own repository (`Path(__file__).resolve().parent.parent`),
matching the portability discipline every prior milestone's
integration test used — the other two repositories are specific to
this machine and are not something a committed test should depend on.

## Known Limitations

- **No true incremental re-parse.** As stated above — `load()` always
  fully rescans; only the write is skipped when nothing changed. A
  future milestone could restructure `RepositoryIndexBuilder` to reuse
  unchanged entries directly, if real usage shows the full-rescan cost
  matters.
- **Single-artifact store only.** `JSONIndexStore` persists
  `RepositoryIndex` alone. `KnowledgeRegistry` and Retrieval metadata
  are not covered — that's M012.
- **Not wired into `Reader`.** `ocom-reader` CLI commands do not
  benefit from caching yet; every invocation still does a full,
  in-memory build exactly as in M009-010. M012 is where this becomes
  real, user-visible behavior.
- **No migration logic.** An incompatible stored format is discarded
  and rebuilt, never migrated forward — appropriate for a single
  format version that has never changed yet; M012 owns real migration
  once there is a second format version to migrate from.
- **Classification conventions remain OCOM-Reader-shaped.** `document_type`
  (ADR/Milestone/README/...), `architecture_sequence`, and `builds_on`
  extraction are unchanged from M006/M007 and still assume this
  project's own naming and header conventions. Verified directly
  against the two external repositories: `document_type` correctly
  falls back to `"Documentation"` for everything in both (no crash, no
  misclassification), and no `architecture_sequence`/`builds_on`
  relations exist for either, since neither uses this project's
  numbering or `**Builds on:**` header convention. Indexing and
  reopening work identically regardless; relation-derived features
  degrade gracefully to text-only search on non-OCOM-Reader
  repositories, an explicit, named boundary rather than a claim of
  full semantic portability.

## Roadmap

```
✅ M001-M010 — OCOM Reader MVP (frozen)
🔄 M011 Repository Loader — done, this document
⬜ M012 Persistent Storage
⬜ M013 Interactive CLI
⬜ M014 Better Retrieval
```
