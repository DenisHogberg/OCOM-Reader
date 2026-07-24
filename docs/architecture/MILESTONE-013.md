# MILESTONE-013: Interactive CLI

**Date:** 2026-07-24
**Status:** Frozen — bare `ocom-reader` launches an interactive session; every one-shot invocation unchanged.
**Builds on:** [MILESTONE-013-DESIGN.md](MILESTONE-013-DESIGN.md), [MILESTONE-012](MILESTONE-012.md)

## Objective

`ocom-reader` with no subcommand launches an interactive session: run
several commands against the same repository without restarting the
process. History, help, in-session repository switching, and graceful
exit — exactly the four things the task asked for, no more.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `run_ask`/`run_search`/`run_related`/`run_explain` (extracted, shared) | `commands.py` | New |
| `InteractiveSession`, `run_interactive` | `interactive.py` | New |
| `--no-cache` unchanged; bare invocation → REPL | `cli.py` | Revised |

`core/`, `interfaces/`, `storage/`, `identity/`, `intelligence/`,
`agent/`, `adapters/`, `normalizers/`, `runtime/`, `main.py`,
`indexer/`, `registry/`, `retrieval/`, `composer/`, `loader/`,
`persistence/` — all unchanged, confirmed via `git diff --stat` (empty
for every one of them). Only `cli.py`/`reader.py` (M009-010's/M012's
own files — `reader.py`'s diff is M012's, untouched again here) were
touched, plus the two new modules.

## A Small Refactor First: `commands.py`

`cli.py`'s four `_run_*` functions needed to be reachable from both
one-shot mode and the new REPL without a circular import (`cli.py` →
`interactive.py` → `cli.py`). Extracted to `commands.py` (renamed
without the leading underscore, now genuinely shared), imported by
both. No behavior change — verified by the full existing `test_cli.py`
suite passing unmodified except for one test whose premise the next
section explains.

## "Context Switching" — Scope Decision

Scoped narrowly to an in-session `use <path>` command that rebuilds
`Reader` against a different repository by path. Named-repository
registration (`repo add`/`repo use` by name) is explicitly M016's job,
built on top of this same primitive — M013 doesn't introduce any
naming/registry concept.

## Commands

```
ask <query>              search <query>
related <registry_id>    explain <query>
use <path>                history
help                       exit / quit
```

Parsed with `shlex.split()` (quoted multi-word queries work like a
real shell — `ask "how does runtime work"`), independent of the
`argparse`-based one-shot parser. Unknown commands, missing arguments,
and malformed quoting all produce a friendly message, never a
traceback — verified by
`test_dispatch_unknown_command`/`test_dispatch_command_missing_required_argument`/`test_dispatch_malformed_quoting_does_not_raise`.

## History

Two independent, deliberately unmerged mechanisms:

- **`history` command** — the session's own `list[str]`, portable,
  deterministic, fully tested.
- **Real terminal up-arrow recall** — `import readline` (wrapped in
  `try/except ImportError` for platforms without it) gives Python's
  `input()` free line-editing/recall on a real TTY. Not unit-testable
  and not tested directly; has no effect on piped/non-TTY stdin, which
  is what every automated test and the real-repository subprocess
  verification below actually exercises.

## Graceful Exit

`exit`/`quit` and `EOFError` (Ctrl-D) both print `"Goodbye."` and
return 0. `KeyboardInterrupt` (Ctrl-C) re-prompts instead of exiting —
matching every standard shell. Any other exception raised while
dispatching a command is caught and rendered as an `Error: ...` line;
the session keeps running — verified by
`test_run_interactive_unexpected_exception_does_not_kill_the_session`,
which injects a failing command handler and confirms the *next*
command still works.

## A Late-Binding Bug Found During Testing (and the fix)

`run_interactive`'s `read_line` parameter originally defaulted to the
`input` builtin directly (`read_line: Callable = input`). Testing
`cli.main([])`'s new no-subcommand path by monkeypatching
`builtins.input` failed — Python binds default argument values once,
at function-definition time, so the monkeypatch never reached the
already-captured reference. Fixed by defaulting `read_line` to `None`
and resolving `input` inside the function body instead, so the lookup
happens at call time. A real, reproduced bug caught by testing through
the actual public entry point (`cli.main()`) rather than only through
`run_interactive()`'s own injectable parameters — named here rather
than silently fixed.

## Test Results

- `tests/test_interactive.py`: **27 passed** — every command via
  `InteractiveSession.dispatch()` directly (including quoting, missing
  args, unknown commands), context switching (successful, missing
  argument, nonexistent path), history, full scripted `run_interactive()`
  sessions (welcome message, `exit`/`quit`/EOF/Ctrl-C, unexpected
  exceptions, prompt reflecting the active repository), persistence
  flag propagation, and real-repository integration (a scripted
  session against this project's own repository, plus two real
  subprocess runs with piped stdin through `python -m ocom_reader —
  one ending with an explicit `exit`, one relying on EOF alone).
- `tests/test_cli.py`: one M009-010 test
  (`test_missing_subcommand_is_rejected`) replaced —its premise (no
  subcommand is an error) is exactly what this milestone changed;
  replaced with `test_missing_subcommand_launches_interactive_mode`,
  asserting the new, correct behavior.
- Full suite: **241 passed** (214 before this milestone + 27 new), no
  regressions.

## Real-Repository Verification

Before writing any test assertions, ran a scripted session (via the
injectable `read_line`/`write` API) against this project's own
repository *and* `/Users/mac/OCOM.wiki`, including a live `use` switch
between them mid-session: `help` → `ask runtime` → `search registry` →
`history` → `use /Users/mac/OCOM.wiki` → `ask architecture` (correctly
answered from the *new* repository) → an unknown command → a
missing-argument command → `exit`. Also ran both real terminal-facing
entry points (`python -m ocom_reader` and the installed `ocom-reader`
console script) with real piped stdin, confirming identical behavior
to the injectable path, including the EOF-without-`exit` case. The
`.ocom/` directory created in `/Users/mac/OCOM.wiki` during this
manual verification was removed afterward — `git status --short` on
that external repository was confirmed empty both before and after.

## Known Limitations

- **`use` only changes the repository path**, not the persistence
  setting (`--no-cache` is fixed for the whole session, decided at
  launch) — no evidence a mid-session toggle is needed; would be
  extra, untested surface.
- **No readline history file** (e.g. `~/.ocom_reader_history`
  persisted across sessions) — only in-session `history`, and only
  real-terminal recall via `readline` within a single run. Persisting
  history across sessions was not asked for and is not implemented.
- **No tab-completion** — not requested by this milestone; a candidate
  for M015 (Rich CLI Experience)'s "shell completion (if practical)."

## Roadmap

```
✅ M001-M012 — OCOM Reader MVP + Repository Independence groundwork (frozen)
✅ M013 Interactive CLI — this document
⬜ M014 Better Retrieval
```
