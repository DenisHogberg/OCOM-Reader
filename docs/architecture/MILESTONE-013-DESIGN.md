# MILESTONE-013: Interactive CLI — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the established M011-014 workflow.
**Builds on:** [MILESTONE-012](MILESTONE-012.md)

## Objective

Bare `ocom-reader` (no subcommand) launches an interactive session: the
user runs several commands against the same repository without
restarting the process. Every existing one-shot invocation
(`ocom-reader ask "..."`, etc.) is unchanged — this milestone only adds
a new code path for the no-subcommand case.

## "Context switching" — scope decision

The task lists `history`, `help`, `context switching`, `graceful exit`
as the four things to add. Multi-repository *registration* (named
repos, `repo add`/`repo use`) is explicitly M016's job. For M013,
"context switching" is scoped narrowly: an in-session `use <path>`
command that points the session at a different repository root by
path, rebuilding `Reader` against it. No naming/registry concept is
introduced here — that's M016, built on top of this same primitive.

## Package: `interactive.py`

One new module, not a package — the REPL is a single cohesive
concern, and reuses `cli.py`'s existing `_run_ask`/`_run_search`/`_run_related`/`_run_explain`
functions directly rather than duplicating output formatting.

```python
class InteractiveSession:
    def __init__(self, repository_root: Path, use_persistence: bool) -> None: ...
    history: list[str]
    reader: Reader
    def dispatch(self, line: str) -> str: ...   # one command in, rendered output out
    def use(self, args: list[str]) -> str: ...  # context switching

def run_interactive(repository_root: Path, use_persistence: bool = True,
                     read_line: Callable[[str], str] = input,
                     write: Callable[[str], None] = print) -> int: ...
```

`read_line`/`write` are injected (default to real `input`/`print`) so
the REPL loop is testable without a real TTY — tests pass a fake
`read_line` that pops from a predetermined command list and raises
`EOFError` when exhausted (matching real `input()`'s end-of-stream
behavior), and capture output via the injected `write` (or `capsys`
against real `print`).

## Commands

| Command | Behavior |
|---|---|
| `ask <query>` | same as `ocom-reader ask` |
| `search <query>` | same as `ocom-reader search` |
| `related <registry_id>` | same as `ocom-reader related` |
| `explain <query>` | same as `ocom-reader explain` |
| `use <path>` | switch the active repository (context switching) |
| `history` | list commands entered this session |
| `help` | list available commands |
| `exit` / `quit` | graceful exit |
| (empty line) | no-op, reprompt |
| anything else | "Unknown command" — never a traceback |

Parsing uses `shlex.split()` (quoted multi-word queries work exactly
like on a real shell, e.g. `ask "how does runtime work"`), not the
`argparse` parser one-shot mode uses — the REPL's per-line grammar is
much simpler (command + rest-of-line) and doesn't need argparse's
subcommand machinery re-invoked on every line.

## History

Two independent mechanisms, deliberately not merged:

- **`history` command** — the session's own `list[str]`, portable,
  deterministic, fully testable. This is the one this milestone's
  tests exercise.
- **Real terminal recall (up-arrow)** — Python's `input()` already
  integrates with the stdlib `readline` module when it's importable;
  `interactive.py` does `import readline` at module load, wrapped in
  `try/except ImportError` (not available everywhere, e.g. some
  Windows setups without `pyreadline`). This is a real-terminal-only
  convenience with no effect on piped/non-TTY stdin — it cannot be
  meaningfully unit-tested, so it isn't; only its harmless absence-of-crash
  is implicitly covered by every other REPL test still passing on this
  machine (where `readline` is available).

## Graceful Exit

- `exit` / `quit` (case-sensitive, matching the CLI's own command
  vocabulary style) — prints a short goodbye, returns 0.
- `EOFError` (Ctrl-D) — same as `exit`, not a crash.
- `KeyboardInterrupt` (Ctrl-C) — prints a newline and re-prompts,
  matching every standard shell's own behavior (Ctrl-C cancels the
  current line, does not exit the shell). A second Ctrl-C behaves the
  same way, every time — there's no "double Ctrl-C force quits"
  special-casing, since that pattern isn't required by the task and
  would be an untested, guessed-at UX addition.
- Any other exception raised while dispatching a command is caught,
  rendered as an error line, and the loop continues — one bad command
  must never kill the session.

## Wiring into `cli.py`

```python
subparsers = parser.add_subparsers(dest="command", required=False)  # was required=True
...
def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        return run_interactive(args.repo, use_persistence=not args.no_cache)
    ...  # existing one-shot dispatch, unchanged
```

`--repo`/`--no-cache` still apply as the REPL's *starting* repository
and persistence setting; `use <path>` only ever changes the active
repository, never the persistence flag mid-session (no evidence a
mid-session toggle is needed, and it would be an extra, untested
surface — `--no-cache` at launch is the one place that's decided).

## Test Plan

- Unit tests on `InteractiveSession.dispatch()` directly (no I/O):
  each command, unknown command, empty line, malformed `use`.
- `run_interactive()` with an injected `read_line`/`write` pair driving
  a scripted session (ask → search → use → ask again → history → exit),
  asserting on captured output and the final return code.
- `EOFError`/`KeyboardInterrupt` handling via a `read_line` fake that
  raises them.
- Real-repository verification (before writing the above): drive a
  scripted session against this project's own repository and the
  external repository used in M011/M012, through both the injectable
  API and a real subprocess with piped stdin (`echo "ask runtime\nexit" | ocom-reader`),
  confirming the piped/non-TTY path works exactly like the injectable
  one.

Proceeding to implementation now.
