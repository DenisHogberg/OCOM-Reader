# Reader M01 — Contract Compliance

**Date:** 2026-07-27 · **Repository:** OCOM-Reader only — Companion was not touched
**Note on numbering:** this "M01" is a new counter for the Reader↔Companion integration track
specifically (Reader M01 → M05 per the roadmap this milestone was requested against). It is
independent of this repository's own existing `MILESTONE-001`–`MILESTONE-021` numbering in
`docs/architecture/` (a different, internal track) — kept as a separate file at the repo
root precisely to avoid the two numbering schemes colliding or being confused for each other.

## Goal

Make Reader fully compatible with `docs/contracts/companion-reader-contract.md` (published by
the Companion repository, Contract Version 1.0) without changing Companion's behavior in any way.

## What changed

Nothing in `~/Downloads/Companion` was touched — verified (`git status`/`git diff` against
Companion's repo show no modifications from this work). Everything below is new, additive
code in OCOM-Reader only:

- **`pyproject.toml`** — added `pyyaml>=6.0` as a dependency. Reader had no YAML parsing
  capability at all before this (confirmed: zero frontmatter/YAML parsing anywhere in the
  existing codebase); Companion's objects are YAML-frontmatter + Markdown, so this is required
  to read them at all.
- **`src/ocom_reader/companion_integration/`** (new package, 4 files):
  - `models.py` — `CompanionStatement` and `CompanionMeeting`, Pydantic models covering exactly
    the fields `companion-reader-contract.md` governs. Both set `model_config =
    ConfigDict(extra="ignore")` **explicitly** — the concrete implementation of "Reader must
    ignore unknown fields," not left to Pydantic's implicit default.
  - `loader.py` — `parse_frontmatter()`, `load_statements()`, `load_meetings()`,
    `find_current_meetings()`. Read-only; tolerates non-Companion Markdown files
    (README.md/REVIEW.md) and malformed/unrelated files by skipping them, never aborting a
    whole load.
  - `signals.py` — `filter_by_signal()` (one signal at a time — see Task 5 below) and
    `render_statement()` (the Kind/Detected Signals display block).
  - `__init__.py` — package docstring pointing back at the contract.
- **`src/ocom_reader/cli.py`** — added a new `companion` subcommand (`companion show <path>`,
  `companion search <root> --signal {metric,question,risk,task,decision}`), dispatched
  independently of Reader's existing `--repo`/workspace machinery (a Companion repository is a
  separate external input, not "the repository being read" in Pipeline A's sense — see
  `companion_integration/__init__.py`'s docstring for why this wasn't grafted onto the
  existing `Reader`/`RetrievalEngine` facade).
- **`tests/test_companion_integration.py`** (new, 14 tests).

No existing file's *behavior* changed — `cli.py`'s existing commands, `Reader`, Pipeline A,
and Pipeline B are all untouched beyond the one new import block and one new dispatch
branch in `main()`.

## Why a new module, not an extension of the existing pipelines

Explored both existing candidates before choosing a third path:
- **Pipeline A** (`indexer/`+`retrieval/`, wired to CLI) has no concept of a structured
  object at all — every file is an opaque Markdown document, classified only by
  filename/path. Retrofitting Statement/Meeting semantics here would fight its own model.
- **Pipeline B** (`adapters/`+`normalizers/`+`core/object.py`) is object-shaped
  (`OCOMObject`) but isn't wired to CLI/search at all, and its `Normalizer` abstraction
  assumes turning one generic Markdown file into one generic `"Document"` object — not a
  fit for a producer (Companion) that already ships a typed, versioned object model of its own.

Companion's Statement/Meeting objects already satisfy their own contract; Reader's job is to
consume that contract precisely, not re-normalize it through either existing pipeline's
different assumptions. A dedicated `companion_integration/` package models the contract
directly.

## Tests performed

**Isolated (synthetic fixtures, 10 tests)** — `tests/test_companion_integration.py`:
old-style Statement (no `detected_signals`) loads safely with `[]`; new-style Statement
(with it) loads correctly; both shapes load together in the same directory tree; an unknown
future field is ignored, not rejected; non-Companion Markdown is skipped, not fatal;
`filter_by_signal` returns independent results per signal, proving no combination logic is
involved; an unknown signal name raises; the exact requested display block format;
`find_current_meetings` correctly excludes a superseded Meeting.

**Real data (4 tests, run directly against `~/Downloads/Companion`, not a copy)**:
- `load_meetings`/`load_statements` against Companion's entire `ai/staging/` tree — 10 real
  Meetings, 500+ real Statements, spanning every milestone from M03 through M07 — all load
  without error. Confirmed both statement shapes genuinely coexist there (some runs
  predate M04.3's `detected_signals`, most postdate it).
- `objects/` (production — nothing promoted there yet in Companion) loads to an empty list,
  not an error.
- `filter_by_signal(..., "task")` against `MTG-00000000-DEMO` returns exactly 17 matches —
  cross-checked against `ai/pipelines/M06_RESULTS.md`'s own independently-reported number
  for the same file, confirming Reader's reimplementation agrees with Companion's.
- `find_current_meetings` against the real 5-times-reprocessed source_hash chain
  (`M03`→`M06`) correctly identifies exactly one current Meeting, at `parser_version
  1.4.0` — the actual latest.

**Regression**: full existing suite, `pytest tests/` — **470 passed** (456 pre-existing +
14 new), zero failures, zero changes to any pre-existing test.

**Manual CLI smoke tests**, real data:
```
ocom-reader companion show <old-style Statement, MTG-00000000-DEM2>   -> Kind: fact, Detected Signals: (none)
ocom-reader companion show <new-style Statement, task_signal>          -> Kind: task_signal, Detected Signals: ✓ task
ocom-reader companion search <full ai/staging tree> --signal decision  -> 13 matches, no errors
ocom-reader companion search <full ai/staging tree> --signal metric    -> 59 matches, no errors
```

## Confirmation against `companion-reader-contract.md`

| Contract requirement | Status |
|---|---|
| Read mandatory fields | ✅ `CompanionStatement`/`CompanionMeeting` model exactly the contract's mandatory set |
| Read optional fields, including `detected_signals` | ✅ all optional, default to empty/None, never required |
| Backward compatibility (old + new Statement together) | ✅ tested synthetically and against real mixed data |
| Ignore unknown fields | ✅ `extra="ignore"` explicit on both models; tested with a synthetic future field |
| `detected_signals` treated as an independent set, never an enumerated combination | ✅ `filter_by_signal()` takes exactly one signal name; no code path compares `detected_signals` as a set/tuple against a fixed combination (see task 5 below) |
| Statement Kind + Detected Signals display | ✅ `ocom-reader companion show` |
| Per-signal search filter | ✅ `ocom-reader companion search --signal {metric,question,risk,task,decision}` |
| Verified against real M07 data | ✅ direct reads of `~/Downloads/Companion/ai/staging/`, not copied fixtures |

## Task 5 — explicit confirmation

No code anywhere in `companion_integration/` compares `detected_signals` against a fixed
combination. `filter_by_signal(statements, signal)` takes a single signal name and checks
`signal in stmt.detected_signals` per statement — the only membership test in the entire
module. Grep-verified: no `==` comparison against a `set(...)`/`frozenset(...)`/tuple
literal of signal names exists in `models.py`, `loader.py`, or `signals.py`.

## What Reader M01 deliberately does not do

Per the roadmap this milestone was requested against — these are explicitly separate,
later milestones, not implicitly bundled in here:
- No rich Signal Search UI (M02) — `companion search` is a working, tested, minimal CLI
  filter, not a polished interface.
- No Object Navigation (M03) — no traversal UI between a Statement and its Meeting/
  resolved entities beyond what `find_current_meetings` needs internally.
- No Timeline View (M04) or Promotion Review UI (M05).
- No integration into Reader's existing `Reader`/`RetrievalEngine`/`AnswerComposer`
  facade (Pipeline A) — `companion` is a fully independent CLI subcommand today. Whether/how
  to unify it with `ask`/`search`/`explain` is a design decision for a later milestone, not
  assumed here.
