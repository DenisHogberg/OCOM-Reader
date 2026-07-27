# Reader CI Design — Product Readiness P02

**Status: design only, until approved. No code, no workflow file added yet.** Every
claim below was checked against the real repository and a real local test run while
writing this — including one live rehearsal of what CI will actually see (Section 5).

## 1. Current requirements for CI

The prior audit (`READER_PRODUCT_READINESS.md`) already established the concrete need:
`.github/` does not exist at all — 512 tests currently pass locally with **zero**
automated verification on push or PR. The goal for P02, per this task's own scope, is
narrow and explicit: confirm Reader installs and its test suite passes, automatically,
on every push and PR. Nothing about code quality (lint), coverage measurement, releases,
or multi-version support is in scope for this first workflow — those are explicitly
excluded by the task and are separate, later CI maturity steps if ever pursued.

## 2. Supported Python versions

- `pyproject.toml` declares `requires-python = ">=3.9"` — a floor, not a range.
- Checked for anything that would make that floor false: no `match`/`case` statements
  (3.10+) anywhere in `src/` (the only `match` occurrences are `re.match(...)` calls and
  prose comments, not the `match` statement); no walrus operator (`:=`) anywhere. Built-in
  generic subscripts (`list[str]`, `dict[str, Any]`, etc.) are valid at runtime on 3.9+
  without needing `from __future__ import annotations` (that import is present in 93 of
  110 source files regardless, for other reasons, but isn't load-bearing for this).
- The actual local development environment already runs **Python 3.9.6**
  (`.venv/bin/python --version`) — the same floor declared in `pyproject.toml`, not a
  different, untested one.
- **Decision: run CI against Python 3.9 only**, matching the declared minimum and the
  real, currently-used dev environment — not "whatever latest happens to be." This is
  the version actually being promised to anyone installing Reader today; validating it
  is more informative for a single-version budget than validating an untested newer
  version instead. No matrix (multiple versions) per this task's explicit exclusion —
  broader version coverage is a legitimate future CI improvement, not part of P02.

## 3. Dependencies

- Runtime: `pydantic>=2.0`, `pyyaml>=6.0` — both unbounded above (no pinned upper
  limit). This is a real, already-flagged reproducibility gap (`READER_PRODUCT_READINESS.md`,
  Section 2) — **not fixed here**, since pinning dependency versions is a separate
  decision from standing up CI, and this task's scope is explicitly the workflow file
  only.
- Test-only: `pytest` is not a declared dependency anywhere in `pyproject.toml` — the
  README's own documented practice is `pip install -e . pytest` as one ad hoc command.
  CI's install step mirrors that exact, already-documented practice rather than
  inventing a new dependency-management convention.
- No environment variables or secrets are required for a clean local test run (checked:
  no `os.environ[...]` required-key access in `config.py`) — the workflow needs no
  `env:` or `secrets:` block.

## 4. Minimal GitHub Actions workflow

`.github/workflows/tests.yml`, exactly four steps, no more:

```yaml
name: Tests

"on": [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.9"

      - run: pip install -e . pytest

      - run: pytest
```

Notes on each choice:
- **Trigger**: `push` and `pull_request`, both with no branch filter — the simplest
  possible trigger set, catching every push and every PR without a branch allow-list to
  maintain.
- **Runner**: `ubuntu-latest` — the standard, no-decision-needed default; nothing in
  Reader is platform-specific.
- **`setup-python`**: pinned to `"3.9"` only, **no `cache: pip`** — caching is explicitly
  excluded from this phase, so it's simply not configured, not configured-and-disabled.
- **Install step**: `pip install -e . pytest` — one command, matching the README's own
  already-documented install/test instructions verbatim, not a new convention.
- **Test step**: bare `pytest`, no flags — validates literally the same command the
  README already tells a human to run, so CI is checking the documented claim, not a
  stricter or looser one.
- **No matrix, no lint, no coverage, no release/publish job** — all explicitly excluded
  by this task; each would be a legitimate separate future step, not part of P02.
- **`"on"` is quoted.** Caught by actually parsing the file with PyYAML before treating
  it as done: a bare `on:` key is YAML 1.1's classic gotcha — PyYAML resolves it to the
  boolean `True`, not the string `"on"`. GitHub's own workflow parser special-cases this
  back to the correct key regardless, so an unquoted `on:` would have worked on GitHub's
  runners too — but quoting it removes the ambiguity outright rather than relying on
  that special-casing, at zero cost.

## 5. Verification (done now, without adding the workflow file yet)

GitHub Actions itself can't be executed locally, but everything the workflow will
actually do was rehearsed directly:

- `pip install -e . pytest` and `pytest` are exactly the commands already run
  successfully throughout this session (512 passed locally).
- **The one thing that could not be assumed**: `tests/test_vector_integration.py`
  conditionally skips 14 real-data tests (`pytestmark_real_vector`) whenever
  `~/Downloads/Vector` doesn't exist — which it won't, on a GitHub-hosted runner. Rather
  than assume this degrades gracefully, it was checked directly: the real
  `~/Downloads/Vector` directory was moved aside temporarily, the full suite was run
  exactly as CI will run it, and it was moved back immediately after. Result: **498
  passed, 14 skipped, zero failures** — confirming CI will go green on a fresh runner
  with no Vector repository present, exactly as the existing `skipif` markers are
  designed to handle, not something newly discovered to be a problem.

## 6. Explicitly out of scope for P02

Per the task's own instructions — not omissions, deliberate exclusions to revisit only
as separate, later, explicitly-approved steps:
- Linting / formatting checks (ruff, flake8, black, mypy).
- Coverage measurement or upload.
- Release or publish automation (PyPI, GitHub Releases).
- Dependency or pip caching.
- Matrix builds (multiple Python versions or OSes).

## What happens after this document is approved

Add exactly one file, `.github/workflows/tests.yml`, containing the YAML in Section 4
above, and nothing else — no README/CHANGELOG/versioning changes bundled in, matching
the isolated-commit discipline used for P01.
