# MILESTONE-015: Rich CLI Experience

**Date:** 2026-07-24
**Status:** Frozen — colored, tabular, adaptive-width, paged output on real terminals; byte-identical plain output everywhere else.
**Builds on:** [MILESTONE-015-DESIGN.md](MILESTONE-015-DESIGN.md), [MILESTONE-014](MILESTONE-014.md), [MILESTONE-013](MILESTONE-013.md)

## Objective

Polish the CLI's presentation — colors, tables, adaptive width,
paging, better help, basic shell completion — with zero new logic in
`Reader`/`Retrieval`/`Registry`/`Indexer`, and zero regression to
existing plain-text output.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `supports_color`, `style`, `render_markdown_inline`, `render_code_block`, `render_markdown`, `render_table`, `terminal_width`/`height`, `maybe_page`, `render_*_rich`, `render_completion_script` | `cli_output.py` | New |
| `preview` field | `composer/models.py` | Revised |
| `preview` population | `composer/answer_composer.py` | Revised |
| `--plain` flag, TTY-gated rich dispatch, `completion` subcommand, improved help epilog | `cli.py` | Revised |
| Richer example text | `interactive.py`'s `HELP_TEXT` | Revised |

`indexer/`, `registry/`, `retrieval/`, `loader/`, `persistence/`,
`reader.py`, `commands.py`, and every M001-M005 package — all
unchanged, confirmed via `git diff --stat` (empty for every one of
them). "No retrieval logic may move into the CLI" holds structurally,
not just by intent: `cli_output.py` imports only data models
(`ComposedAnswer`, `RetrievalMatch`, `RegistryEntry`), never
`RetrievalEngine`/`KnowledgeRegistry`/`RepositoryIndexBuilder`.

## The One Rule: Auto-Plain When Not a TTY

`rich = sys.stdout.isatty() and not args.plain`. Every existing test
in `test_cli.py`/`test_interactive.py` runs under `capsys`/subprocess
pipes — never a TTY — so the entire pre-M015 suite passing unmodified
(291/291, no changes needed to any test beyond the new M015-specific
ones) **is** the backward-compatibility regression test, not just a
claim about it.

## No New Dependencies

Still just `pydantic` in `pyproject.toml`. Colors: raw ANSI escapes.
Tables: hand-rolled column alignment. Paging: stdlib `pydoc.pager()`.
"Syntax-highlighted code blocks" was scoped down to *visually
distinguished* framing (dim/boxed), not per-language token coloring —
a real highlighter would be this project's first third-party
dependency, not clearly asked-for enough to justify. Shell completion
is a static, hand-written bash function (subcommand names + flags),
not `argcomplete`-powered dynamic completion — also to avoid a new
dependency, and explicitly named as the "practical" version the task's
own wording allowed for.

## Markdown Rendering — Grounded in a Real New Field

`ComposedAnswer`/`ExplainedDocument` had no document body text to
render before this milestone. `DocumentRef.preview` (new,
`str = ""`) is populated in `AnswerComposer._document_ref` exactly
like `title`/`path` already are — copied from `RepositoryIndex`, never
generated. `cli_output.py` renders it beneath each document's
title/score line through `render_markdown` (bold, italic, inline code,
fenced code blocks). Most previews are plain prose with nothing to
highlight — an honest reflection of what's actually indexed (M006
never indexed full document bodies), not a missing feature.

## Tables

`search`/`related` moved from bullet lists to aligned tables
(`# | registry_id | score` / `# | registry_id | type`), width-adaptive
via `terminal_width()`, truncating the widest column when the terminal
is narrow — confirmed against a real, narrower pseudo-terminal (below),
not just a hardcoded `max_width` in a unit test.

## A Real Bug Found During Real-Terminal Verification

`pydoc.pager()` was originally gated on `sys.stdout.isatty()` alone.
Verifying against a real pseudo-terminal (`script -q /dev/null python3
-m ocom_reader ... ask ...`) reproduced an actual hang: `TERM` was
unset in that environment, `pydoc` fell back to its interactive
"Press RETURN to continue" prompt, and with no real user able to
respond, the process hung indefinitely — recoverable only by `kill -9`.
Fixed by additionally requiring `sys.stdin.isatty()` **and** a usable
`TERM` (`not in (None, "", "dumb")`) before paging activates — `can_page`
in `cli.py`. Re-verified after the fix: the same command completes
immediately in the same environment. `test_ask_never_hangs_when_stdin_is_not_a_real_tty_even_if_stdout_is`
is the regression test. Named here in full rather than silently
patched, the same discipline M013 used for its own late-binding `input`
bug.

## Scope Decision: Interactive REPL Gets Help Text Only, Not Color/Tables

Given the paging hang risk above, wiring color/tables into
`interactive.py`'s already-running read-eval-print loop was judged
riskier than the time available to properly verify it — deferred
explicitly rather than shipped under-tested. M013's REPL gains richer
`help` text (one-line examples per command) this milestone; color and
tabular REPL output are named as future work, not silently dropped.

## Test Results

- `tests/test_cli_output.py`: **32 passed** — `supports_color` under
  every input combination, `style`/`render_markdown_inline`/`render_code_block`/`render_markdown`
  on synthetic snippets (including plain text with nothing to
  highlight), `render_table` alignment and width truncation,
  `maybe_page` with `pydoc.pager` mocked (never a real interactive
  pager in a test), every `render_*_rich` function's structure and
  empty-input handling, and completion script generation.
- `tests/test_cli.py`: **5 new** — `completion bash`, `--plain` forcing
  plain output even with a simulated TTY, color activating with a
  simulated TTY, `NO_COLOR` disabling color while keeping the table,
  and the paging-hang regression test.
- Full suite: **291 passed** (254 before this milestone + 32 + 5), no
  regressions — the entire pre-existing suite unmodified.

## Real-Terminal Verification

Before writing any test, ran through an actual pseudo-terminal
(`script -q /dev/null`, not just simulated `isatty()` mocks) against
this project's own repository and `/Users/mac/OCOM.wiki`:

- Colors rendered correctly (ANSI codes visible and correctly scoped
  to headers/titles/previews).
- Table column truncation correctly activated on the narrower
  pseudo-terminal width (`registry_id` truncated to `registry_…`, not
  wrapped or misaligned).
- `completion bash` printed a valid bash completion function.
- `--plain` and `NO_COLOR` both verified to suppress color while
  `--plain` also suppressed tables/paging.
- The paging hang (see above) was found and fixed during this exact
  verification pass, before any test asserted the broken behavior as
  correct.
- `git status --short` on `/Users/mac/OCOM.wiki` confirmed empty
  before and after (no `.ocom/` or other artifact left behind from
  `--no-cache` runs).

## Known Limitations

- **Color/tables not yet wired into the interactive REPL** — scoped
  out this milestone for the reason stated above; `help` text is
  richer, but `ask`/`search`/`related`/`explain` output inside a REPL
  session is still plain, unchanged from M013.
- **"Syntax highlighting" is visual framing, not per-language
  coloring** — no tokenizer/grammar, no new dependency.
- **Shell completion is bash-only, subcommand/flag names only** — no
  dynamic value completion (e.g. real `registry_id`s), no zsh/fish
  support.
- **Paging's `TERM` guard is a heuristic**, not a perfect detector of
  "a human can actually respond to a pager prompt" — chosen because it
  reproduced and fixed a real, observed hang; not proven to catch
  every possible unusual terminal environment.

## Roadmap

```
✅ M001-M014 — OCOM Reader MVP + Repository Independence + Better Retrieval (frozen)
✅ M015 Rich CLI Experience — this document
⬜ M016 Multi-Repository Workspace
⬜ M017 Plugin Architecture
⬜ M018 Web UI
⬜ M019 Optional LLM Layer
⬜ M020 Product Release
```
