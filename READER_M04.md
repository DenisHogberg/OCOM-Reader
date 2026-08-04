# Reader M04 — Promotion Review UI

**Date:** 2026-07-27 · **Repository:** OCOM-Reader only — Vector was not touched
**Builds on:** `READER_M01.md`/`READER_M02.md`/`READER_M03.md`, and a full design
review performed *before* any code was written — see `READER_M04_DESIGN.md`. Same
`vector_integration/` package, no changes to `VectorStatement`'s field set, no change
to Contract Version (still 1.0).

## Goal

Let a human reviewer browse Statements grouped by `statement_kind` — a review queue,
not a promotion pipeline. Reader displays; a human still makes every promotion
decision. Named `vector review`, deliberately not `vector promotion`, to keep that
distinction in the command itself, not just the docs.

## Process followed (as requested, matching M03's discipline)

1. Design review first — `READER_M04_DESIGN.md`, including a Standing Principles
   section and a Design Principle now treated as binding for every future milestone:
   *Reader MUST NOT infer new semantic objects. Reader MAY group, sort, and visualize
   contracted Vector data. Reader MUST NOT create Promotion Candidates, Promotion
   Scores, Promotion Labels, or any derived workflow state absent from the Vector
   Contract.*
2. Implemented `vector_integration/promotion.py`.
3. Added the `vector review <root>` CLI command.
4. Wrote unit tests (13 new).
5. Ran the full regression suite.
6. Ran a manual CLI smoke test against the real `~/Downloads/Vector` repository.
7. This document and `docs/vector-integration.md`, written last, only after 2-6 were
   all confirmed working.

## What changed

All additive, in `~/Downloads/OCOM-Reader` only:

- **`vector_integration/promotion.py`** (new) — `group_by_statement_kind()`,
  `render_promotion_review()`, and two private ordering helpers
  (`_timestamp_seconds()`, `_meeting_sections()`). No new model field, no new loader.
- **`cli.py`** — one new subcommand, `vector review <root>`.
- **`docs/vector-integration.md`** — new "beyond Contract v1.0" note (M04 reuses M03's
  `meeting_date`, adds nothing new), a new "What Reader does NOT do" entry restating
  the Design Principle, one new CLI example.
- **`tests/test_vector_integration.py`** — 13 new tests (512 total in the suite).

## The two points flagged for extra attention, and how they were verified

**Empty results.** Confirmed at three levels, not just asserted:
- Unit: `render_promotion_review([], [])` renders all seven groups at `(0)` /
  `(none)`, no exception (`test_render_promotion_review_shows_all_seven_groups_even_when_empty`,
  `test_render_promotion_review_completely_empty_input_never_errors`).
- Real-data smoke test: `vector review` against a path with **no** Vector data at all
  (`/tmp/does-not-exist-xyz`) — output below, no traceback:

  ```
  TASK (0)

  (none)

  DECISION (0)
  ...
  ```

**Sort stability.** `_statement_sort_key()` returns `(timestamp_seconds, statement.id)`
and the Meeting-level sort key includes `meeting_id` as a tiebreaker — both ties are
broken by an immutable, unique identifier, never left to input order.
`test_render_promotion_review_deterministic_tie_break_same_timestamp` constructs two
Statements at the identical Meeting and timestamp, renders the list both forward and
reversed, and asserts byte-identical output — this is checked, not assumed.

## A correction made during implementation, not just at design time

The design doc's original `O(n)` complexity claim for rendering was already corrected
during the design-review revision (to `O(n log n)`, once Meeting/timestamp ordering was
decided) — restated here because it's a real, load-bearing property confirmed by the
tests above, not just a documentation fix.

One additional thing verified only now, during implementation: the design doc guessed
"real meetings are comfortably under 20 minutes" for the `timestamp`-format edge case
(`MM:SS` breaks past 99 minutes as a plain string compare). That guess was already
wrong when checked (the longest real `timestamp` is `32:02`) — `promotion.py` parses
`timestamp` to seconds via `_timestamp_seconds()` rather than string-comparing it, so
this edge case doesn't rely on the guess being right, but it's worth recording that the
guess itself was inaccurate.

## Tests performed

**Isolated (synthetic fixtures)**: exact-value bucketing (including `unclassified` for
`None` and an ad-hoc bucket for an unrecognized future `statement_kind` value, never
merged into `other`); all seven always-shown groups render even at zero; Meeting-date
ordering (including undated-sorts-last); Statement-timestamp ordering within a Meeting;
an unresolvable `meeting_ref` renders under `(unknown meeting)`, last, not dropped; the
deterministic-tie-break case above; a malformed `timestamp` renders without raising; an
unknown `statement_kind` value is appended after the seven known groups, not interleaved.

**Real data**, against `~/Downloads/Vector` directly:
- `task_signal` count for `MTG-00000000-DEMO` — **7**, matching the same number
  independently confirmed in `READER_M02.md`, `M06_RESULTS.md`, and
  `READER_M04_DESIGN.md`.
- Full `ai/staging/` tree, filtered through `filter_to_current_meetings` first: this
  Meeting's title appears in exactly the groups it has Statements in (5 of the 7), and
  **never more than once within any single group's block** — the exact bug class M03
  found (one duplicate section per stale reindex run) does not reappear here.

**Regression**: `pytest tests/` — **512 passed** (499 from M01-M03, 13 new), zero
failures.

**Manual CLI smoke test, real data** (Standing Principle #4 — required, not optional):
- `vector review ai/staging/MTG-00000000-DEMO` — `TASK (7)`, matches the known number.
- `vector review ~/Downloads/Vector` (whole repo root) — group counts sum to **414**,
  exactly the real current-meeting Statement total (verified independently via a
  separate script call, not just trusted from the rendered output); 5 real current
  meetings; `MTG-00000000-DEMO`'s title appears exactly 5 times total (once per group
  it belongs to), not 30 times (5 groups × its 6-run reindex chain) — confirming the
  required `filter_to_current_meetings` step is doing its job at real scale, not just
  in the single-meeting-directory case.
- Nonexistent root — all seven groups render at `(0)`/`(none)`, no traceback.

## Confirmation against completion criteria

| Criterion | Status |
|---|---|
| Groups Statements by promotion likelihood without Reader deciding anything | ✅ `vector review` — grouped by Vector's own `statement_kind`, no Reader-side classification |
| No new Vector contract fields | ✅ zero new fields; reuses M03's already-flagged `meeting_date` |
| No write-back | ✅ pure read/render, no write path anywhere in `promotion.py` |
| No hidden heuristics | ✅ exact-value bucketing and deterministic sort only; Vector's own combination→label table explicitly not reimplemented |
| Real-repo testing discipline (unit → regression → smoke) | ✅ all three, in that order, this document |
| Contract discrepancies documented | ✅ `docs/vector-integration.md` restates `meeting_date`'s beyond-contract status for its second consumer |

## What Reader M04 deliberately does not do

- No candidate labeling richer than the six `statement_kind` values (no "Task with
  KPI"-style combination labels) — explicitly rejected in the design review as a
  reimplementation of Vector's own analysis logic.
- No filtering flag (`vector review --only task,risk`) — raised as a legitimate later
  addition during design review, out of scope for M04 itself.
- No object creation, no promotion, no write-back — Reader only displays what Vector
  has already produced and already classified.
