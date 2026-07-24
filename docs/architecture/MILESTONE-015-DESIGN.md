# MILESTONE-015: Rich CLI Experience — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the established workflow.
**Builds on:** [MILESTONE-014](MILESTONE-014.md), [MILESTONE-013](MILESTONE-013.md)

## Objective

Polish the CLI's presentation — colors, tables, adaptive width,
paging, better help, basic shell completion — with zero new logic
in `Reader`/`Retrieval`/`Registry`/`Indexer`, and zero regression to
existing plain-text output. "No retrieval logic may move into the
CLI" is read literally: every change here is presentation of data
these layers already produce.

## The One Rule That Shapes Everything: Auto-Plain When Not a TTY

Colors, tables, and paging only ever activate when `sys.stdout.isatty()`
is true (and `NO_COLOR` isn't set, and `--plain` wasn't passed) — the
same convention `git`, `ls --color=auto`, and most modern CLIs already
use. Piped or redirected output (exactly what every existing test, and
every script that shells out to `ocom-reader`, does) gets **byte-identical
plain text to before this milestone**. This is what makes "keep all
existing commands backward compatible" verifiable rather than just
asserted — the existing `test_cli.py`/`test_interactive.py` suites,
unmodified, are the backward-compatibility regression test.

## New Module: `cli_output.py`

Pure presentation, no Reader/Retrieval/Registry/Indexer imports beyond
the data models it renders (`ComposedAnswer`, `RetrievalMatch`,
`RegistryEntry`). Every function takes an explicit `color: bool`
parameter rather than checking `sys.stdout.isatty()` itself — keeps
every function pure and directly testable, the same "inject the
decision, keep the function testable" pattern `interactive.py`'s
`read_line`/`write` already established in M013. `cli.py`/`interactive.py`
compute the actual `color` bool once, at startup.

```python
def supports_color(no_color_flag: bool) -> bool: ...       # isatty() and not NO_COLOR env and not no_color_flag
def style(text: str, *codes: str, color: bool) -> str: ...  # ANSI wrap, no-op if color=False
def render_markdown_inline(text: str, color: bool) -> str: ...  # **bold**, *italic*, `code`
def render_code_block(text: str, color: bool) -> str: ...       # ```fenced``` -> visually distinguished, dim-boxed
def render_table(headers: list[str], rows: list[list[str]], color: bool, max_width: int) -> str: ...
def terminal_width() -> int: ...              # shutil.get_terminal_size().columns
def maybe_page(text: str, enabled: bool) -> None: ...  # pydoc.pager() when enabled and long enough
```

## No New Dependencies

`pyproject.toml` has depended on `pydantic` alone since Phase 1. This
milestone adds none:

- **Colors**: raw ANSI escape codes (`\033[1m`, `\033[36m`, ...) — no
  `colorama`/`rich`/`click` needed on POSIX terminals, which is this
  project's only tested target.
- **Tables**: hand-rolled column alignment (stdlib `str.ljust`/width
  math) — no `tabulate`.
- **Paging**: stdlib `pydoc.pager()`, which already knows how to find
  `$PAGER`/`less`/`more` and already no-ops sanely when not a TTY.
- **"Syntax-highlighted code blocks"**: scoped down to *visually
  distinguished* (dim background/box, monospace framing), not
  per-language-grammar token coloring — a real syntax highlighter
  (e.g. `pygments`) would be this project's first third-party
  dependency ever, and wasn't asked for explicitly enough to justify
  that. Named here rather than silently under-delivered.
- **Shell completion**: scoped to a static, hand-written bash
  completion script listing subcommand names and flags (`ocom-reader
  completion bash`) — not `argcomplete`-powered dynamic completion
  (would be a new dependency). "If practical" in the task's own
  wording; this is the practical, zero-dependency version.

## Markdown Rendering — What There Actually Is to Render

`ComposedAnswer`/`ExplainedDocument` don't currently carry any
document body text — only title/path/reasons/score (M006 never
indexed full document content; M009-010 never surfaced `preview`).
There is nothing markdown-shaped to render yet. Rather than add a
feature with nothing to point it at, `DocumentRef` gains one new,
well-grounded field:

```python
class DocumentRef(BaseModel):
    ...
    preview: str = ""   # NEW — copied from DocumentIndexEntry.preview at compose time
```

Populated in `AnswerComposer._document_ref` exactly like `title`/`path`
already are (read from `RepositoryIndex`, never generated). `cli_output.py`
renders each document's `preview` beneath its title/score line, through
`render_markdown_inline`/`render_code_block` — so `**emphasis**`,
`` `inline code` ``, and any fenced code block that happens to appear
in a document's opening paragraph render distinctly. Most previews are
plain prose with nothing to highlight — that's an honest reflection of
what's actually indexed, not a missing feature.

## Tables

`search`/`related` output moves from bullet lists to aligned tables
(`# | registry_id | score` / `# | registry_id | entry_type`). `ask`/`explain`'s
Evidence/Related Documents sections gain a preview line per document
(see above) but keep their existing per-document block layout — a
table doesn't suit variable-length reason lists well, so it isn't
forced there. Column widths respect `terminal_width()`, truncating the
widest column (typically `registry_id`) rather than wrapping unevenly.

## Paging

`ask` output (which can run to 25+ lines on a well-connected real
repository, per M009-010's own real-repo verification) pages through
`pydoc.pager()` when `color` is true (i.e., a real TTY) and the
rendered text exceeds `terminal_height`. Never pages in plain/piped
mode — a script capturing `ocom-reader ask ...`'s output must still get
the whole thing back immediately, unchanged from before this milestone.

## Improved Help

`argparse`'s `epilog` gains a short usage example block; the
interactive `help` command's text gains one-line examples per command.
No structural change to argument parsing.

## Shell Completion

`ocom-reader completion bash` prints a static bash completion function
(subcommand names, `--repo`/`--no-cache`/`--plain` flags) to stdout —
the user redirects it into their own completion setup
(`ocom-reader completion bash >> ~/.bash_completion`, documented in the
milestone doc, not automated — this milestone doesn't modify the
user's shell configuration on its own, which would be a real side
effect requiring explicit permission per this session's own action
policy).

## Test Plan

- `cli_output.py` unit tests: `supports_color()` under every input
  combination (TTY flag, `NO_COLOR`, `--plain`), `style()` no-ops when
  `color=False`, `render_markdown_inline`/`render_code_block` on
  synthetic markdown snippets (bold, italic, inline code, fenced
  block, plain text with nothing to highlight), `render_table` column
  alignment and width truncation, `maybe_page` (mocked `pydoc.pager`,
  never called when `enabled=False`).
- Backward compatibility: every existing `test_cli.py`/`test_interactive.py`
  test re-run unmodified (non-TTY by construction) — these are the
  regression suite for "no behavior change in plain mode."
- New CLI-level tests: `--plain` flag forces plain output even if
  color were somehow available; `NO_COLOR` env var respected;
  `completion bash` subcommand output.
- Real-repository verification (before writing the above): run `ask`/`search`/`related`/`explain`
  with color forced on against this project's own repository and at
  least one other real repository, visually confirming readable ANSI
  output and correct table alignment.

Proceeding to implementation now.
