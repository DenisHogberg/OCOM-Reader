# MILESTONE-012: Persistent Storage

**Date:** 2026-07-24
**Status:** Frozen — versioned `.ocom/` persistence implemented, wired into `Reader` as the default, verified against three real repositories.
**Builds on:** [MILESTONE-012-DESIGN.md](MILESTONE-012-DESIGN.md), [MILESTONE-011](MILESTONE-011.md)

## Objective

Real, versioned, on-disk persistence for everything `Reader` builds —
`RepositoryIndex`, `KnowledgeRegistry`, and Retrieval metadata — using
the exact layout requested: `.ocom/{metadata,index,registry,retrieval}.json`,
`metadata.json` carrying `storage_version` (int), `reader_version`,
`repository_root`, `created_at`, `last_updated`.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `StorageMetadata`, `FormatCompatibility`, `MigrationError` | `persistence/models.py` | Implemented |
| `.ocom/` path layout | `persistence/paths.py` | Implemented |
| `MIGRATIONS`, `migrate_to_current`, `CURRENT_STORAGE_VERSION` | `persistence/migrations.py` | Implemented |
| `PersistentStore` | `persistence/store.py` | Implemented |
| `RepositoryLoader` (revised — read/diff-only) | `loader/repository_loader.py` | Revised |
| `Reader(use_persistence=True)` | `reader.py` | Revised |
| `ocom-reader --no-cache` | `cli.py` | Revised |

`core/`, `interfaces/`, `storage/`, `identity/`, `intelligence/`,
`agent/`, `adapters/`, `normalizers/`, `runtime/`, `main.py`,
`indexer/`, `registry/`, `retrieval/`, `composer/` — all unchanged,
confirmed via `git diff --stat` (empty for every one of them). Only
`reader.py`/`cli.py` (M009-010's own files) and `loader/` (M011's own
package) were revised; `persistence/` is new.

## Deviations from MILESTONE-012-DESIGN.md

- **`RepositoryLoader`'s constructor changed**, not just its internals.
  The design doc said "public API unchanged"; that held for the four
  *methods* (`load`, `reopen`, `detect_changes`, `check_compatibility`
  — identical signatures and return types) but not the constructor:
  M011's `RepositoryLoader(store: Optional[JSONIndexStore])` took an
  externally-shared, hash-keyed store; M012's `PersistentStore` is
  inherently per-repository (`.ocom/` lives inside each
  `repository_root`), so there is nothing left to inject or share
  across repositories. `RepositoryLoader()` now takes no arguments.
  Disclosed precisely here rather than glossed over as "unchanged."
- Everything else in the design doc was implemented as planned:
  storage layout, `metadata.json` schema, the `persistence/` package
  shape, the "Reader is the only writer" decision, the retrieval.json
  placeholder rationale, and the migration scaffold.

## Architecture

```
Reader.__init__(repository_root, use_persistence=True)
        │
        ▼  RepositoryLoader().load(repository_root)
   .ocom/ present & unchanged? ──yes──► reuse stored RepositoryIndex
        │no
        ▼
   RepositoryIndexBuilder(repository_root).build()  (fresh, full scan)
        │
        ▼
   RegistryBuilder().build(index)   — always fresh, never loaded back
        │
        ▼
   PersistentStore(repository_root).save(index, registry)
        │
        ▼
   RetrievalEngine + AnswerComposer, as in M009-010
```

`RepositoryLoader` (M011, revised) is now **read/diff-only** — it
never writes. Only `Reader` writes, because it's the only component
holding all three artifacts (Index, Registry, soon Retrieval metadata)
at once; a partial write (fresh `index.json` paired with a stale
`registry.json`) would silently describe an inconsistent snapshot,
since `KnowledgeRegistry` entries assume 1:1 correspondence with
`RepositoryIndex` entries. `metadata.json` is written last, so its
mere existence always means a complete, consistent snapshot.

`KnowledgeRegistry` is never read back from `.ocom/` for actual use —
`registry.json` is written for persistence/inspection, but `Reader`
always rebuilds `KnowledgeRegistry` fresh from whichever `RepositoryIndex`
it ends up with (`RegistryBuilder.build()` is cheap, pure, and
deterministic). This sidesteps any "is the stored registry still valid
for this index" staleness question entirely — there's no such question
to ask.

## Storage Format

```json
// .ocom/metadata.json
{
  "storage_version": 1,
  "reader_version": "0.1.0",
  "repository_root": "/abs/path",
  "created_at": "2026-07-24T06:09:48.337301+00:00",
  "last_updated": "2026-07-24T06:09:48.337301+00:00"
}
```

`reader_version` comes from `importlib.metadata.version("ocom-reader")`
at save time — never hardcoded. `created_at` is set once (carried
forward from the existing `metadata.json` on every resave, if present);
`last_updated` refreshes on every save. `.ocom/` is added to
`.gitignore`.

`retrieval.json` currently holds a minimal placeholder
(`{"ranking_config": {}}`) — `RetrievalEngine` (M008) has no
persistent state of its own today. The file exists now, format-versioned,
specifically so M014's configurable ranking pipeline has somewhere to
write real settings without needing a new migration to add the file.

## Reader Behavior Change (the real, user-visible part of this milestone)

`Reader(repository_root)` now writes to disk by default — a genuine
change from M009-010/M011, where `Reader`/`ocom-reader` were
guaranteed 100% read-only. This is the intended purpose of "Persistent
Storage," not an accidental side effect, and it's the reason M011
deliberately deferred any Reader integration until this milestone.
`Reader(repository_root, use_persistence=False)` preserves the exact
original zero-I/O behavior; `ocom-reader --no-cache <command>` exposes
the same choice at the CLI. Verified identical `ComposedAnswer` output
between cached and uncached construction
(`test_reader_answer_is_identical_with_and_without_persistence`).

## Test Results

- `tests/test_persistence.py`: **19 passed** — `.ocom/` layout, `exists()`,
  index/registry round-trip, retrieval-metadata placeholder,
  `metadata.json` field correctness (`created_at` stable across
  resaves, `last_updated` advances), compatibility (missing, valid,
  newer-than-current), migration scaffold (chaining, no-op, missing-migration
  error), never writing outside the target repository, no mutation of
  its inputs, and real-repository round-trip.
- `tests/test_repository_loader.py`: **13 passed** — rewritten for the
  M012-revised `RepositoryLoader` (no more `JSONIndexStore`): reopen/load
  with nothing stored, reuse-when-unchanged, real-change detection
  through `load()`, confirming `load()` never writes, `detect_changes()`
  unchanged from M011, compatibility delegation, and real-repository
  integration.
- `tests/test_reader_pipeline.py`: **5 new** persistence tests —
  default persistence creates `.ocom/`, `use_persistence=False` writes
  nothing, identical answers cached vs. uncached, a real file change is
  picked up on reconstruction, and a second construction with nothing
  changed reuses the exact stored snapshot byte-for-byte.
- `tests/test_cli.py`: **2 new** — `ask` creates `.ocom/` by default,
  `--no-cache` skips it.
- Full suite: **214 passed**, no regressions. 193 before this milestone
  (M011), `test_repository_loader.py` rewritten from 18 to 13 tests to
  match the revised `RepositoryLoader` (-5), plus 19 new in
  `test_persistence.py`, 5 new in `test_reader_pipeline.py`, and 2 new
  in `test_cli.py`: 193 − 5 + 19 + 5 + 2 = 214.

## Real-Repository Verification (Three Repositories)

Run manually, before writing any test assertions, against the same
three repositories used in M011:

| Repository | Result |
|---|---|
| `OCOM-Reader` (this project) | `.ocom/` created, `storage_version=1`, `reader_version=0.1.0`, deterministic across reconstruction |
| `/Users/mac/Downloads/OCOM` (366 docs) | Same — `.ocom/` created, deterministic |
| `/Users/mac/OCOM.wiki` (7 docs) | Same — `.ocom/` created, deterministic |

Additionally, on a scratch copy of the wiki repository (never the
original): edited a file, confirmed `Reader`'s persisted `index.json`
content_hash updated to match a fresh independent scan; confirmed
`use_persistence=False` never creates `.ocom/`. `git status --short`
on both external repositories was confirmed empty before and after
every run — nothing was ever written outside each repository's own
`.ocom/`, and the two external repositories were left exactly as found
(their own `.ocom/` directories were removed after verification, since
those repositories don't have `.ocom/` in their own `.gitignore`).

## Known Limitations

- **Reader always resaves on construction**, even when nothing changed
  — `RepositoryLoader.load()` returning the previous index unchanged
  still triggers a fresh `PersistentStore.save()` (only `last_updated`
  and, harmlessly, identical content get rewritten). This is a
  simplicity/correctness tradeoff, not a performance-tuned path — the
  alternative (Reader tracking "did anything really change" itself,
  duplicating logic `RepositoryLoader` already computed) was judged
  not worth the complexity without evidence it matters. Named as a
  candidate for later optimization, not fixed here.
- **No real migration exists yet.** Only `storage_version = 1` has
  ever existed; `MIGRATIONS` is empty. The chaining mechanism is
  proven with a synthetic test migration, not a real one — there is
  nothing real to migrate from.
- **`retrieval.json` is a placeholder**, as stated above — genuinely
  empty of content until M014.
- **`.ocom/` always lives inside `repository_root`.** For repositories
  the caller doesn't want written into, `use_persistence=False` is the
  only escape hatch this milestone provides; there is no alternate,
  external cache-directory option (M011 had one; M012 deliberately
  replaced it with the requested in-repository layout).

## Roadmap

```
✅ M001-M010 — OCOM Reader MVP (frozen)
✅ M011 Repository Loader
✅ M012 Persistent Storage — this document
⬜ M013 Interactive CLI
⬜ M014 Better Retrieval
```
