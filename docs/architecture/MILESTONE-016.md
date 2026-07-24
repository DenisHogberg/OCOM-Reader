# MILESTONE-016: Multi-Repository Workspace

**Date:** 2026-07-24
**Status:** Frozen — named repository registration, listing, active-repository switching, and removal; retrieval untouched.
**Builds on:** [MILESTONE-016-DESIGN.md](MILESTONE-016-DESIGN.md), [MILESTONE-015](MILESTONE-015.md), [MILESTONE-012](MILESTONE-012.md), [MILESTONE-011](MILESTONE-011.md)

## Objective

Name repositories, list them, switch which is active, forget one —
pure bookkeeping layered strictly above `Reader`, never touching
`Retrieval`/`Registry`/`Indexer`. Per review: the workspace only ever
answers "which repositories exist, which is active, where does its
storage live" — it never influences what a query returns.

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

`WorkspaceManager` resolves a name to a `repository_root: Path` and
hands that path to an ordinary, unmodified `Reader(repository_root)`
call — the exact same construction every prior milestone already
uses. It never constructs `RetrievalEngine`/`KnowledgeRegistry`/`AnswerComposer`
and never imports them.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `WorkspaceEntry`, `WorkspaceState`, `WorkspaceError` | `workspace/models.py` | New |
| `WorkspaceManager` | `workspace/workspace_manager.py` | New |
| `repo add/list/use/remove`, `--repo` resolution order, `--workspace-file` | `cli.py` | Revised |
| `repo add/list/use/remove` REPL commands | `interactive.py` | Revised |

`indexer/`, `registry/`, `retrieval/`, `composer/`, `loader/`,
`persistence/`, `reader.py`, and every M001-M005 package — all
unchanged, confirmed via `git diff --stat` (empty for every one of
them, beyond what M012/M014/M015 already introduced). `cli_output.py`'s
`render_table`/`style` were reused as-is for `repo list`, no changes
needed there either.

## "Isolated per-repository persistence" was already true

M012 made `.ocom/` live inside each `repository_root`, keyed by
nothing but that directory — two workspace entries pointing at
different paths already cannot collide. This milestone didn't need to
build isolation, only prove it:
`test_two_workspace_repositories_get_independent_ocom_directories` and
`test_switching_active_repository_produces_independent_answers` both
construct two real `Reader`s through the workspace and assert their
`.ocom/` contents and `ComposedAnswer`s are independent, not merely
plausible.

## `storage_path`/`is_initialized`: the one narrow exception

Both call into `persistence.paths`/`persistence.store.PersistentStore.exists()`
— pure path arithmetic and a file-existence check, never persistence
I/O (no index/registry save or load) and never retrieval. This is
exactly what "where does its storage live" (the review's own phrasing)
asks the workspace to answer, and nothing more.

## Behavior Decisions

- **First repository added becomes active automatically** — a
  workspace with exactly one repository and no active one would
  otherwise force an extra `use` call for the common single-repo case.
- **`remove()` never deletes a repository's `.ocom/` or any files** —
  reversible bookkeeping only. If the removed entry was active,
  `active` is cleared, never silently reassigned to another entry.
- **`--repo` resolution order**: explicit `--repo` (bypasses the
  workspace entirely) → active workspace repository → `Path(".")`.
  This is the same "auto-fallback to prior behavior" discipline M015
  used for TTY detection — a user who never runs `repo add`/`repo use`
  sees zero change from M015's own behavior. `--repo`'s default
  changed from `Path(".")` to `None` specifically so "not passed" is
  distinguishable from "passed as `.`".
- **`workspace.json` is versioned from day one** (`version: 1`),
  matching M012's own discipline, without a migration scaffold this
  early — the same restraint M012 itself used at launch.

## A Test-Hygiene Fix Along the Way

`WorkspaceManager()`'s default location is `~/.ocom_reader/workspace.json`
— every CLI invocation now constructs one, even a plain `ask` with an
explicit `--repo`, if only to check the file doesn't exist. Verifying
this against the existing test suite surfaced that `test_cli.py`/`test_interactive.py`
would otherwise touch the *real* home directory on every run. Fixed
with an autouse fixture patching `Path.home()` to a sibling of `tmp_path`
(not a subdirectory — several fixtures index `tmp_path` itself as a
repository, and a workspace file living inside the indexed repo would
be a needless, if harmless, overlap) plus a `--workspace-file` override
flag (hidden from `--help`, real usage never needs it) for the
subprocess-based tests, which can't inherit a monkeypatch across a
process boundary. No test in this project's suite has ever touched the
real home directory, and this keeps it that way.

## Test Results

- `tests/test_workspace.py`: **27 passed** — `add` (registration,
  nonexistent path, duplicate name, first-add-becomes-active,
  second-add-doesn't-steal-active), `list`, `use` (switch, unknown
  name), `remove` (unregister, clears active only if it was active,
  never deletes files, unknown name), `resolve` (by name, via active,
  neither present, unknown name), `storage_path`/`is_initialized`
  (before/after a real `Reader` use), state persistence across
  `WorkspaceManager` instances, isolation between two repositories,
  and real-repository integration.
- `tests/test_cli.py`: **8 new** — `repo add`/`list`, default naming
  from the directory, `repo use` + bare `ask` resolving to the active
  repository, explicit `--repo` bypassing the workspace, `repo remove`
  never deleting files, an unknown `repo use` reporting an error
  (exit code 1), and the cwd fallback with nothing registered.
- `tests/test_interactive.py`: **6 new** — `repo add`/`list`, `repo use`
  switching the session's `Reader` (and a subsequent `ask` answering
  from the new repository), `repo remove` never deleting files, an
  unknown `repo use` reporting an error without crashing the session,
  `repo` with no subcommand, and an empty workspace's `repo list`.
- Full suite: **332 passed** (291 before this milestone + 27 + 8 + 6),
  no regressions.

## Real-Repository Verification

Before writing any test, ran the full CLI workflow against this
project's own repository and `/Users/mac/OCOM.wiki` with an isolated
`--workspace-file`: `repo add . --name OCOM-Reader` → `repo add
/Users/mac/OCOM.wiki --name wiki` → `repo list` (correctly showing
`OCOM-Reader` as `active=True`, `wiki` as `initialized=no`) → bare
`ask runtime` (correctly answered from `OCOM-Reader`, the active repo)
→ `repo use wiki` → bare `ask architecture` (correctly answered from
the wiki repo instead) → `repo remove wiki` → `repo list` (confirming
it's gone). Repeated the same sequence through the interactive REPL's
`repo` commands with identical results. `git status --short` on
`/Users/mac/OCOM.wiki` confirmed empty before and after every run.

## Known Limitations

- **No workspace-wide search** — `ask`/`search`/etc. still operate
  against exactly one repository at a time (the active one, or an
  explicit `--repo`). Querying across all registered repositories at
  once was not asked for and is not implemented.
- **`repo list`'s REPL output stays plain** (no color/table), per
  M015's own deferred-scope decision for interactive rendering — not
  silently expanded here.
- **No path validation beyond "is a directory"** — `repo add` doesn't
  check the path actually contains any Markdown documentation; an
  empty directory registers successfully and simply produces
  ungrounded answers, consistent with how `Reader` has always behaved
  on an empty repository since M009-010.

## Roadmap

```
✅ M001-M015 — OCOM Reader MVP + Repository Independence + Better Retrieval + Rich CLI (frozen)
✅ M016 Multi-Repository Workspace — this document
⬜ M017 Plugin Architecture
⬜ M018 Web UI
⬜ M019 Optional LLM Layer
⬜ M020 Product Release
```
