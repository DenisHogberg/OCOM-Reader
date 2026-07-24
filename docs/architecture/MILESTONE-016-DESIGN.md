# MILESTONE-016: Multi-Repository Workspace — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the established workflow.
**Builds on:** [MILESTONE-015](MILESTONE-015.md), [MILESTONE-012](MILESTONE-012.md), [MILESTONE-011](MILESTONE-011.md)

## Objective

Name repositories, list them, switch which one is active, forget one
— pure bookkeeping above `Reader`, never touching `Retrieval`/`Registry`/`Indexer`.
Per review: the workspace only ever answers "which repositories exist,
which is active, where does its storage live" — it never influences
what a query returns.

## Layering (as specified)

```
Workspace Manager
        ↓
Repository Loader (M011)
        ↓
Persistent Storage (M012)
        ↓
Reader (M009-010)
        ↓
Retrieval (M008) → Composer (M009-010)
```

`WorkspaceManager` sits *above* `Reader`, resolving a name to a
`repository_root: Path` and handing that path to a normal, unmodified
`Reader(repository_root)` call — the exact same construction path
every prior milestone already uses. `WorkspaceManager` never
constructs a `RetrievalEngine`, `KnowledgeRegistry`, or `AnswerComposer`
itself, and never imports them.

## "Isolated per-repository persistence" is already true

M012 made `.ocom/` live inside each `repository_root`, keyed by
nothing but that directory. Two workspace entries pointing at two
different paths already cannot interfere — there is no shared cache
keyed by name or index for them to collide in. This milestone doesn't
need to build isolation; it needs to prove it (see Test Plan).

## Package: `workspace/`

```
workspace/
    __init__.py
    models.py             WorkspaceEntry, WorkspaceState
    workspace_manager.py  WorkspaceManager
```

```python
class WorkspaceEntry(BaseModel):
    name: str
    path: str          # resolved absolute path
    added_at: datetime

class WorkspaceState(BaseModel):
    version: int = 1   # versioned from day one, matching M012's own
                        # discipline — no migration scaffold yet, since
                        # (as with M012 at launch) only version 1 has
                        # ever existed; not over-built ahead of a real need.
    entries: list[WorkspaceEntry] = []
    active: Optional[str] = None
```

```python
class WorkspaceManager:
    def __init__(self, state_path: Optional[Path] = None) -> None: ...
    def add(self, name: str, path: Path) -> WorkspaceEntry: ...
    def list(self) -> list[WorkspaceEntry]: ...
    def use(self, name: str) -> WorkspaceEntry: ...
    def remove(self, name: str) -> None: ...
    def active(self) -> Optional[WorkspaceEntry]: ...
    def resolve(self, name: Optional[str] = None) -> Path: ...
    def storage_path(self, name: str) -> Path: ...      # .ocom/ location — path only
    def is_initialized(self, name: str) -> bool: ...    # has that .ocom/ actually been built yet
```

`storage_path`/`is_initialized` are the one deliberate, narrow
exception to "workspace never touches persistence": both call into
`persistence.paths`/`persistence.store.PersistentStore.exists()` —
pure path arithmetic and a file-existence check, not persistence I/O
(no save/load of an actual index) and not retrieval. This is exactly
what "where its storage lives" (the review's own phrasing) asks the
workspace to be able to answer.

## Behavior Decisions

- **`add()`**: rejects a nonexistent path or a duplicate name
  (`WorkspaceError`, a new small exception type). The *first* repository
  added automatically becomes active (no active repo existed yet to
  conflict with) — a defensible default, not a guess: a workspace with
  exactly one repository and no active one would otherwise force an
  extra `use` call for the common single-repo case.
- **`remove()`**: unregisters the entry only — never deletes the
  repository's `.ocom/` directory or any files. Removing a repository
  from the workspace is reversible bookkeeping; deleting its
  persisted index would be a destructive action this milestone was not
  asked to perform and won't guess at. If the removed entry was
  active, `active` is cleared (not silently reassigned to another
  entry) — explicit "no active repository" over a guessed one.
- **`resolve(name=None)`**: `name` given → look it up (raises if
  unknown); else the active entry's path (raises if none is active).
  This is the *one* call site `cli.py`/`interactive.py` use.

## CLI Integration

```bash
ocom-reader repo add ~/Projects/OCOM --name OCOM
ocom-reader repo add ~/Projects/MyProject
ocom-reader repo list
ocom-reader repo use MyProject
ocom-reader repo remove MyProject
ocom-reader ask "Runtime"
```

`--name` is optional on `add`; when omitted, the directory's own
`.name` (basename) is used — matching the task's own example
(`ocom-reader repo add ~/Projects/OCOM` with no `--name` still needing
*some* name to register under).

**`--repo` resolution order** (new — `--repo`'s default changes from
`Path(".")` to `None` so "not passed" is distinguishable from "passed
as `.`"):

1. `--repo <path>` explicitly passed → used directly, workspace never
   consulted. Zero behavior change for anyone who always passes
   `--repo` (or never touches the workspace feature at all).
2. Else, an active workspace repository exists → its path.
3. Else → `Path(".")`, exactly M009-010 through M015's behavior.

This preserves the same "auto-fallback to old behavior" discipline
M015 used for TTY detection: a user who never runs `repo add`/`repo use`
sees no change whatsoever.

`repo list` renders a table (via `cli_output.render_table`, already
built in M015) with columns `name | path | active | initialized` —
`initialized` from `is_initialized()`, not a new retrieval concept.

## Interactive REPL Integration

`interactive.py` gains `repo add <path> [name]` / `repo list` / `repo use <name>` /
`repo remove <name>` commands, alongside the existing M013 `use <path>`
command (unchanged — still a lightweight, unregistered path switch).
Per M015's own deferred-scope decision, REPL `repo list` output stays
plain (no color/table) — consistent with keeping the REPL's rich
rendering scope exactly where M015 left it, not silently expanding it
here.

## Storage Location

`~/.ocom_reader/workspace.json` by default (a new, distinctly-named
path — not reusing M011's now-removed `default_cache_dir()`, which no
longer exists after M012 replaced `JSONIndexStore`). Configurable via
constructor for tests (`tmp_path`-scoped, never the real home
directory during any automated test).

## Test Plan

- Unit: `add`/`list`/`use`/`remove`/`active`/`resolve`/`storage_path`/`is_initialized`,
  every error path (nonexistent path, duplicate name, unknown name on
  `use`/`remove`, `resolve()` with nothing active), first-add-becomes-active,
  `remove()` of the active entry clears active without guessing a
  replacement, state persists across `WorkspaceManager` instances
  (same `state_path`), never deletes a repository's own files.
- CLI: `repo add/list/use/remove`, `--repo` resolution order (explicit
  beats active beats cwd fallback), backward compatibility (no
  workspace commands ever run → identical behavior to M015).
- Isolation: two repositories registered and used in sequence produce
  independent, non-interfering `.ocom/` directories and independent
  `Reader.answer()` results — proving M012's per-path isolation holds
  at the workspace level, not just asserting it.
- Real-repository verification (before writing the above): register
  this project's own repository and at least one other real repository
  used throughout M011-M015, switch between them via `repo use`, and
  confirm `ask` answers correctly reflect whichever is active.

Proceeding to implementation now.
