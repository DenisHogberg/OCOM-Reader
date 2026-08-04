# Reader M03 — Object Navigation

**Date:** 2026-07-27 · **Repository:** OCOM-Reader only — Vector was not touched
**Builds on:** `READER_M01.md` (Contract Compliance), `READER_M02.md` (Signal Explorer) —
same `vector_integration/` package, no changes to `VectorStatement`'s field set, no
change to Contract Version (still 1.0).

## Goal

Teach Reader to navigate objects and their relationships, not just individual
Statements: Object View, reverse navigation from a Statement to what it mentions,
Cross-Meeting View, a text-only Relationship Browser, and an Entity Timeline.

## What changed

All additive, in `~/Downloads/OCOM-Reader` only:

- **`vector_integration/models.py`** — added `KNOWN_OBJECT_TYPES` (the 11 non-Statement/
  Meeting Vector types) and a new `VectorObject` model covering Vector's *common* object
  frontmatter (id/type/title/tenant/owner/status/lifecycle/confidence/source/
  relationships/references/evidence/tags), with an `aliases()` method reading the
  `alias:<form>` tags convention. Added `VectorMeeting.meeting_date` (optional). **Both
  are explicitly flagged as beyond Contract v1.0's stated scope** — see
  `docs/vector-integration.md`'s "Supported contract version" section and "What Reader
  does NOT do" below.
- **`vector_integration/loader.py`** — added `load_objects()`, globbing every `*.md` and
  filtering by `type in KNOWN_OBJECT_TYPES` (no shared filename prefix across 11 types,
  unlike Statement/Meeting's `STM-`/`MTG-` convention), plus `_NON_OBJECT_FILENAMES` to
  skip `README.md`/`REVIEW.md`.
- **`vector_integration/navigation.py`** (new) — `find_object()`, `linked_statements()`,
  `linked_meeting_ids()`, `render_object_view()` (Task 1); `mentions()`/
  `render_mentions()` (Task 2); `meetings_mentioning()`/`render_cross_meeting_view()`
  (Task 3); `render_relationship_tree()`, a cycle-safe plain-text walk (Task 4);
  `render_entity_timeline()` (Task 5); and `filter_to_current_meetings()` — see "A real
  bug, found by actually running this" below.
- **`cli.py`** — four new subcommands (`vector object`, `vector mentioned-in`,
  `vector relationships`, `vector timeline`), and `vector show` gained an optional
  `--root` flag that additionally prints a Mentions block.
- **`docs/vector-integration.md`** — new "beyond Contract v1.0" section, three new
  limitations, five new CLI examples.
- **`tests/test_vector_integration.py`** — 17 new tests (499 total in the file *and*
  suite — see Regression below).

## Naming deviation from the milestone's own example, documented as in M02

The milestone's illustrative CLI (`ocom-reader object OBJ-123`) is a bare top-level
command. Kept consistent with M01/M02 instead: everything here lives under the existing
`vector` subcommand namespace (`vector object`, `vector mentioned-in`,
`vector relationships`, `vector timeline`), for the same reason `vector summary` was
named that way in M02 — a Vector repository is a separate, external input, not "the
repository being read" in Pipeline A's sense, and mixing a bare `object` command into
Reader's own top-level command set would blur that line.

## A real bug, found by actually running this against real data (not synthetic fixtures)

Vector's own M03 (Source Identity & Idempotent Import) reprocesses the same real meeting
multiple times as its pipeline improves — same `source_hash`, different
`parser_version` — leaving several superseded Meeting objects with the same title
sitting side by side in `ai/staging/`. Running `vector object` against Vector's real
*repository root* (not a single meeting's staging directory, which is what M01/M02's
tests and the earlier drafts of this milestone's own tests used) surfaced this directly:
Jordan's (`PTN-00000000-DEMO`) Linked Statements showed **12** and Meetings showed
**6** — a 6x overcount, one for each reindex run of the same real meeting
(`MTG-00000000-DEMO`'s own supersedes chain, confirmed via
`test_find_current_meetings_against_real_supersedes_chain` in M01). The correct, real
numbers (confirmed independently via `grep` before writing any code) are **2** Statements
in **1** meeting.

Fixed with `navigation.filter_to_current_meetings()`, which reuses
`loader.find_current_meetings()` — the identical `supersedes`-chain resolution Vector's
own pipeline already relies on for idempotent import — rather than inventing a second
notion of "current" on Reader's side. `object`, `mentioned-in`, and `timeline` all filter
through it before aggregating across meetings. `show --root` (reverse navigation from one
already-selected Statement) is unaffected, since it never aggregates across meetings in
the first place. A dedicated test, `test_real_filter_to_current_meetings_collapses_reindex_chain`,
reproduces the bug against Vector's real full `ai/staging/` tree and confirms the fix
brings the count back down to the correct 2/1.

## Beyond Contract v1.0 — an honest gap, not silently worked around

`vector-reader-contract.md` v1.0 governs Statement fields only (plus two Meeting fields).
Object Navigation genuinely needed two things outside that: the `VectorObject` model
(Vector's common object frontmatter has no published contract at all yet) and
`Meeting.meeting_date` (needed for Entity Timeline's chronological sort; no
contract-covered field substitutes — `Statement.created` is Reader's ingestion date, not
the meeting's date, and `Statement.timestamp` is only an offset within the recording).
Both are read defensively (optional, tolerant of absence) and both are flagged in
`docs/vector-integration.md` with a concrete recommendation: Vector should publish a
second contract or a v1.1 addendum covering the common object schema, the same way
Statement's fields are covered today.

## Discrepancies between the milestone's illustrative examples and Vector's real model

- The milestone's example uses a `Person` type and a `Finance Team` object — Vector has
  no `Person` type (its people-shaped types are `Partner` and `Employee`) and no
  `Finance Team` object exists in real data. `VectorObject`/`load_objects()` are built
  against Vector's actual 11 non-Statement/Meeting types (`KNOWN_OBJECT_TYPES`), not the
  milestone's illustrative names.
- The milestone's Relationship Browser example uses `works_with` as a relationship type.
  Vector's own documented relationship vocabulary doesn't include it (checked against
  `docs/relationships-and-references.md`), and real objects have zero relationships
  populated regardless. `render_relationship_tree()` is deliberately generic — it walks
  whatever `type`/`target` pairs are present without hardcoding any type name — so this
  doesn't block the implementation, but it does mean the Relationship Browser has
  nothing real to walk yet (see next section).

## An honest limitation: no real relationships or aliases to validate against

Checked directly (not assumed): all 6 real Vector objects
(`PTN-00000000-DEMO--angelina.md`, `PTN-00000000-DEM2--bondarenko.md`,
`PTN-00000000-DEM3--nevidomyi.md`, `PTN-00000000-DEM4--olena.md`,
`EMP-00000000-DEMO--denys.md`, `EMP-00000000-DEM2--oleh.md`) have empty `relationships`,
`references`, `evidence`, and no `alias:` tags. This means:

- **Object View's Aliases/Relationships sections** render correctly (`(none)`) against
  real data, but are only exercised showing actual content against synthetic fixtures
  (`test_render_object_view_with_aliases_and_relationships`).
- **The Relationship Browser** has nothing to walk in real data at all — tested
  exclusively against synthetic fixtures, including a same-type tree
  (Partner → works_with → Company → owns → Project) and a cycle
  (A → B → A, confirmed to terminate rather than recurse forever).

By contrast, **Linked Statements, Mentions, Cross-Meeting View, and Entity Timeline** all
have real data behind them — Vector's real `references` do point from Statements to
Partner/Employee objects — and are tested against Vector's actual
`ai/staging/MTG-00000000-DEMO` in addition to synthetic fixtures.

## Post-review refactor (same day, before M04)

A review pass asked four verification questions (relationships-absence safety,
Reader's ability to run on today's Vector data without relationships/aliases,
whether new relationships would require reindexing, and O(n) vs O(n²) in the new
CLI commands). Answering them empirically surfaced two small, real inefficiencies in
`navigation.py`, fixed immediately as plain refactors (no new functionality, no
behavior change):

- **`linked_meeting_ids()`** used a `list` for its `seen` accumulator, checked with
  `not in seen` — O(n·m) (n = linked Statements, m = distinct meetings for that
  object) rather than O(n), and inconsistent with `filter_to_current_meetings()`,
  which already used a `set` for the same kind of check. Changed to a `set` for
  membership plus a separate list to preserve first-seen order.
- **`render_object_view()`** computed `linked_statements()` twice — once directly,
  once again inside the old `linked_meeting_ids(object_id, statements)`. Fixed by
  changing `linked_meeting_ids()`'s signature to take an already-computed Statement
  list (`linked_meeting_ids(statements)`) instead of recomputing it from an object id,
  so a caller who already has the list only pays for it once. This is the one public
  API change in this refactor; `meetings_mentioning()` and all tests were updated to
  match.

Verified before and after with an instrumented real-data run
(`~/Downloads/Vector`, `PTN-00000000-DEMO`): `linked_statements` calls inside
`render_object_view` dropped from 2 to 1, output unchanged (2 Linked Statements, 1
Meeting). Full suite re-run: **499 passed**, unchanged.

## Tests performed

**Isolated (synthetic fixtures)**: `find_object` hit/miss; `linked_statements`/
`linked_meeting_ids` across multiple meetings; Object View's full block with and without
aliases/relationships; reverse navigation (`mentions`/`render_mentions`) resolving and
correctly skipping an unresolvable reference; Cross-Meeting View; the Relationship
Browser's tree format, its cycle-termination behavior (verified it shows the closing
back-reference then stops, rather than silently truncating), and an unresolvable-target
case; Entity Timeline's date-sort (including an undated meeting sorting last, never
dropped); `filter_to_current_meetings` collapsing a synthetic supersedes chain.

**Real data**: Object View for the real `PTN-00000000-DEMO` (2 Statements, 1 Meeting,
confirmed via direct `grep` before writing the test); Cross-Meeting View for the real
`EMP-00000000-DEM2` (5 Statements, 1 Meeting); reverse navigation from a real Statement
known to reference `PTN-00000000-DEMO`; Entity Timeline using the real
`meeting_date: '2026-07-27'` on `MTG-00000000-DEMO`; and the reindex-collapsing fix
itself, reproduced against the real, full `ai/staging/` tree.

**Manual CLI smoke tests**, real data: `vector object`, `vector mentioned-in`,
`vector relationships`, `vector timeline` against `PTN-00000000-DEMO` under the full
`~/Downloads/Vector` root (this is what surfaced the reindex-overcounting bug above,
before the fix and after); `vector show --root` printing a correct Mentions block; a
nonexistent object id producing a clean `Error: ...` on stderr with exit code 1, not a
traceback.

**Regression**: `pytest tests/` — **499 passed** (482 from M01+M02, 17 new), zero
failures.

## Confirmation against completion criteria

| Criterion | Status |
|---|---|
| Object View (Type/Name/Linked Statements/Meetings/Aliases/Relationships) | ✅ `vector object` |
| Reverse Navigation (Statement → mentions → Object) | ✅ `vector show --root` |
| Cross-Meeting View | ✅ `vector mentioned-in` |
| Relationship Browser (text tree, no graphical visualization) | ✅ `vector relationships` |
| Entity Timeline | ✅ `vector timeline` |
| Contract v1.0 compatibility preserved | ✅ no field added/removed on `VectorStatement`; full M01+M02 test suite passes unmodified |

## What Reader M03 deliberately does not do

- No resolution of the "no real relationships/aliases" gap above — that requires real
  Vector data to change, not Reader.
- No object-level change history — Entity Timeline is a timeline of *mentions*, not of
  field-level changes to the object itself (Reader has no access to Vector's git
  history); documented explicitly in `render_entity_timeline`'s docstring and
  `docs/vector-integration.md` to avoid overstating what's actually shown.
- No integration into Reader's own `ask`/`search`/`explain`/`Reader` facade — `vector`
  remains a fully independent CLI subcommand, unchanged from M01/M02.
- No promotion, no object creation — Reader only displays what Vector has already
  produced.
