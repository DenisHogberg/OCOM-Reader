# MILESTONE-012: Persistent Storage — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the approved M011-014 workflow (design first, then implement/verify/test, checkpoint after the milestone lands).
**Builds on:** [MILESTONE-011](MILESTONE-011.md)

## Objective

Give the pipeline real, versioned, on-disk persistence for everything
`Reader` builds — `RepositoryIndex`, `KnowledgeRegistry`, and Retrieval
metadata — using the exact layout requested:

```
.ocom/
    metadata.json
    index.json
    registry.json
    retrieval.json
```

`.ocom/` lives **inside the indexed repository** (`repository_root/.ocom/`),
the same idiom as `.git/` — a deliberate change from M011's
`JSONIndexStore`, which always wrote *outside* the target repository.
M011 avoided writing into a repository it didn't necessarily own; M012
makes it a first-class, expected local-state directory (like `.git/`
or `.venv/`), which is what the requested layout implies. `.ocom/` is
added to `.gitignore` as part of this milestone.

## metadata.json

```json
{
  "storage_version": 1,
  "reader_version": "0.1.0",
  "repository_root": "/abs/path",
  "created_at": "2026-07-24T...",
  "last_updated": "2026-07-24T..."
}
```

`storage_version` is an integer (not M011's `"1.0"` string) — this
milestone's schema, not M011's. `reader_version` comes from
`importlib.metadata.version("ocom-reader")` at save time (reads
`pyproject.toml`'s version through the installed package metadata, no
hardcoded string). `created_at` is set once, on first save;
`last_updated` is refreshed on every save.

## Package: `persistence/`

```
persistence/
    __init__.py
    models.py       StorageMetadata, FormatCompatibility (reused from loader/), MigrationError
    paths.py         .ocom/ layout — the four file paths, as pure functions of repository_root
    migrations.py    MIGRATIONS registry (version N -> N+1 functions) + migrate_to_current()
    store.py         PersistentStore — save()/load()/exists()/check_compatibility()
```

`PersistentStore.save(index, registry, retrieval_metadata)` writes all
four files together (`index.json` from `RepositoryIndex.model_dump(mode="json")`,
`registry.json` from `KnowledgeRegistry.model_dump(mode="json")`,
`retrieval.json` — see below, `metadata.json` last, once the other
three succeeded, so a metadata.json that exists always describes a
complete, consistent snapshot).

`PersistentStore.load()` returns `None` if `metadata.json` is absent,
raises nothing on a version mismatch — it migrates
(`migrate_to_current`) when `storage_version` is older than current,
or reports incompatible via `check_compatibility()` if migration isn't
possible (e.g. a *newer* stored version than this Reader understands).

## Retrieval metadata (`retrieval.json`)

`RetrievalEngine` (M008) is stateless today — it holds no data beyond
the `RepositoryIndex`/`KnowledgeRegistry` it's constructed with, no
cache, no configuration. There is, honestly, nothing substantive to
persist yet. `retrieval.json` is created now, format-versioned, with a
minimal schema (`{"ranking_config": {}}`) specifically so M014's
configurable ranking pipeline has a place to write real settings into
*without* needing a new migration to add the file — directly serving
"this keeps future migrations straightforward." This is named
explicitly, not left implicit.

## Migration scaffold

```python
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}  # {from_version: fn(data) -> migrated_data}

def migrate_to_current(data: dict, from_version: int) -> dict:
    version = from_version
    while version < CURRENT_STORAGE_VERSION:
        migrate_fn = MIGRATIONS.get(version)
        if migrate_fn is None:
            raise MigrationError(f"No migration path from storage_version {version}")
        data = migrate_fn(data)
        version += 1
    return data
```

Only `storage_version = 1` exists, so `MIGRATIONS` starts empty — there
is nothing to migrate from yet. The mechanism itself is exercised by
one test that registers a synthetic `0 -> 1` migration function
against a hand-built legacy-shaped payload, proving the chaining logic
works structurally, the same way M011 tested format-incompatibility
recovery before any real incompatible format existed.

## Relationship to M011 (`loader/`)

`RepositoryLoader`'s public API (`load`, `reopen`, `detect_changes`,
`check_compatibility`) is unchanged. Internally, it is updated to use
`persistence.PersistentStore` instead of `loader.JSONIndexStore` for
the actual save/load I/O — `JSONIndexStore` and `FORMAT_VERSION`
(M011's deliberately-superseded placeholder) are removed, exactly as
M011's own docstring said would happen. `loader/models.py`'s
`ChangeSet` is untouched and still Index-only, still useful standalone.
`FormatCompatibility` is now defined once in `persistence/models.py`
and re-exported from `loader/` for backward compatibility with M011's
own public API.

## Reader Integration (the actual behavior change this milestone makes real)

`Reader.__init__` gains persistence as the **default**:

```python
Reader(repository_root, use_persistence: bool = True)
```

When `True` (default): `Reader` builds `RepositoryIndex`/`KnowledgeRegistry`
through `RepositoryLoader` + `PersistentStore`, reusing `.ocom/` when
present and compatible, writing it (Index + Registry + a currently-empty
Retrieval metadata) when absent or changed. When `False`: identical to
M009-010's original behavior — pure in-memory build, zero disk I/O,
preserved for callers who need a guaranteed-read-only Reader (e.g. a
future multi-repo scenario inspecting a repository without adopting it).

**This is a real, user-visible behavior change**, flagged explicitly:
`ocom-reader` CLI commands will, from this milestone on, create
`.ocom/` inside whatever repository they're pointed at by default. This
is the intended, stated purpose of "Persistent Storage" — not an
accidental side effect — but it is a new disk-write where none existed
before M012, so it's called out here rather than left for the reader to
discover. CLI gains a `--no-cache` flag mapping to `use_persistence=False`.

## Test Plan

- `persistence/`: unit tests for `PersistentStore` round-trip (all four
  files), `metadata.json` field correctness (`created_at` set once,
  `last_updated` refreshed), missing/partial `.ocom/` handling,
  version-mismatch → migration path, migration scaffold with a
  synthetic migration, `.ocom/` never written outside `repository_root`.
- `loader/`: existing M011 tests re-verified against the new backend
  (same public API, same behavior).
- `reader.py`/`cli.py`: `use_persistence` default-True behavior,
  `use_persistence=False` preserves M009-010's exact zero-I/O
  behavior, `--no-cache` CLI flag, determinism across cached and
  uncached runs producing identical `ComposedAnswer`s.
- Real-repository verification (before writing the above): run against
  this project's own repository and the two other repositories used in
  M011's verification, confirming `.ocom/` is created correctly,
  reopened correctly, and reused when nothing changed.

Proceeding to implementation now.
