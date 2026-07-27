# READER_M04_DESIGN.md — Promotion Review UI

**Status: design review only. No code written yet.** This document exists specifically
to catch architectural problems before implementation, per explicit request before
starting M04. Grounded in the actual current state of `~/Downloads/Vector`, checked
directly (not assumed) while writing this — see the numbers cited throughout.

**All four open questions from the first draft are now decided** — see "Open Questions
(decided)" at the end. This revision folds those decisions into every section above it,
rather than leaving them as a separate pending list.

**Scope note on numbering**: the original roadmap (`READER_M01.md`, `READER_M02.md`)
listed M04 as "Timeline View" and M05 as "Promotion Review UI." Timeline View was
delivered early, folded into M03 Task 5 (Entity Timeline). M04 is therefore renumbered
to cover what was originally M05: Promotion Review UI. Confirmed with the user before
writing the first draft of this document.

---

## Goal

Let a human reviewer browse Statements grouped by how likely they are to warrant
promotion to a real object (Task/Decision/Risk/...), **without Reader promoting
anything itself.** Reader only displays; a human still makes every promotion decision,
the same way Vector's own `ai/staging/` review already works
(`docs/ai-collaboration.md`'s write-back governance). This is a review queue, not a
promotion pipeline — reflected directly in the CLI name (`vector review`, decided below)
rather than left as something the docs have to clarify after the fact.

## Design Principle

Added at the user's explicit request, as a standing rule for this and every future
Reader milestone, not just M04:

> **Reader MUST NOT infer new semantic objects.**
>
> **Reader MAY** group, sort, and visualize contracted Vector data.
>
> **Reader MUST NOT** create Promotion Candidates, Promotion Scores, Promotion Labels,
> or any derived workflow state that is absent from the Vector Contract.

This is the concrete, checkable form of a principle this project has followed since
M01 without stating it this bluntly: Vector owns analysis; Reader owns navigation and
visualization. Every function proposed below is checked against this rule explicitly,
not just against "does it work."

## Standing Principles (mandatory, not just for M04)

Confirmed by the user as binding rules for this and every future Reader milestone that
touches `vector_integration/` — checked against the design above, not just asserted:

1. **No new contract fields.** Reader consumes only what `vector-reader-contract.md`
   already publishes, or an already-flagged beyond-contract exception (`meeting_date`,
   from M03) — never a field proposed *for* a Reader feature's convenience. **Checked**:
   M04 introduces zero new fields; its one beyond-contract dependency (`meeting_date`)
   is M03's existing one, reused, not new (see Compatibility).
2. **No write-back to Vector.** Read-only, no exceptions. **Checked**: Data Flow above
   has no write path; Public API is pure functions over already-loaded data.
3. **No hidden heuristics.** If a grouping needs a guess Reader can't ground in an exact,
   already-published field value, show the raw data instead of inventing a
   classification. **Checked**: `group_by_statement_kind` buckets by exact literal
   field value; Meeting/timestamp ordering is a deterministic sort, not an inference;
   the rejected alternative (reimplementing Vector's signal-combination table) was
   rejected specifically because it would have been a heuristic Reader has no
   contracted basis for.
4. **Testing discipline, in order**: unit tests (synthetic fixtures) → full regression
   suite → manual CLI smoke test against the real `~/Downloads/Vector` repository — the
   same sequence M03 actually followed. The Test plan below is updated to state the
   manual smoke-test step explicitly rather than leaving it implicit; it is not
   optional; it is what caught M03's reindex-duplication bug, which no synthetic
   fixture surfaced.
5. **Document every contract discrepancy.** Any field Reader depends on that isn't in
   the formal contract must stay explicitly flagged (in `docs/vector-integration.md`
   and the milestone report) until Vector formally updates the contract — never let it
   quietly become "assumed stable." **Checked**: `meeting_date`'s beyond-contract status
   is restated in Compatibility and Vector Contract assumptions below, not just in
   M03's report.

## The finding that shapes everything below: Vector has no persisted Promotion Candidate data at all

Checked directly before writing anything else in this document:

```
$ find ~/Downloads/Vector -iname "*promot*"
./ai/pipelines/M05_PROMOTION_READINESS.md
$ ls ~/Downloads/Vector/schemas/     # no promotion/candidate schema
$ grep -rn "promot|candidate" ingest_transcript.py   # no persisted candidate object,
                                                       # "candidate" only means entity-
                                                       # name/meeting/alias candidates
```

Vector's own `M05_PROMOTION_READINESS.md` (Vector-side numbering — a different M05 than
Reader's) is a **pure analysis document**: a signal-combination → candidate-label table,
applied by hand to already-persisted `detected_signals`, explicitly "no objects created,
no pipeline code changed." Nothing from that table is written to disk anywhere. There is
no `Promotion Candidate` object type, no schema, no field on Statement carrying a
candidate label. The only real, persisted, contract-covered fields Reader can build on
are `Statement.statement_kind` (closed 6-value enum, already contracted) and
`Statement.detected_signals` (closed 5-value set, already contracted).

**This is the central architectural constraint for M04**: there is nothing new to read.
Whatever "Promotion Review UI" means, it has to be built entirely as a *presentation*
layer over fields Reader has had full, contracted access to since M01 — not as a new
data source, and not as a reimplementation of Vector's own candidate-labeling logic (see
Design Principle above).

## Public API

Proposed additions to `vector_integration/`, all pure functions over already-loaded data
(no new loader, no new model field):

```python
# promotion.py (new)
REVIEW_GROUPS = ("task_signal", "decision_signal", "risk_signal", "metric", "fact", "other")

def group_by_statement_kind(statements: list[VectorStatement]) -> dict[str, list[VectorStatement]]:
    """Buckets by the existing, single-valued, closed statement_kind field —
    never by a detected_signals combination (Design Principle). Statements
    with no statement_kind at all go in a separate 'unclassified' bucket,
    never silently dropped and never merged into 'other' (a real classifier
    output, a different thing from data absence)."""

def render_promotion_review(
    statements: list[VectorStatement], meetings: list[VectorMeeting]
) -> str:
    """All six REVIEW_GROUPS shown, always, in that fixed order, even at zero
    count (decided #3 — consistency over hiding non-actionable groups).
    Within each group: sub-sectioned by Meeting, Meetings ordered by
    meeting_date (undated last — same convention as render_entity_timeline),
    Statements within a Meeting ordered by Statement.timestamp (decided #4).
    Reuses render_statement() per-item from M02 — no new per-Statement
    rendering primitive.

    Callers MUST pass `statements` already filtered through
    navigation.filter_to_current_meetings(statements, meetings) — see
    Failure Modes: without it, this inherits the exact reindex-duplication
    bug M03 found and fixed for Object Navigation, here manifesting as the
    same Meeting section appearing once per reprocessing run instead of
    once."""
```

CLI: **`vector review <root>`** (decided #1 — not `vector promotion`, not
`vector candidates`; Reader doesn't promote or decide, it reviews). A later,
explicitly out-of-scope-for-M04 filter flag (`vector review --only task,risk`) was
raised as a possible follow-up, not part of this milestone.

## Data Flow

```
load_statements(root)                    [existing, M01]
load_meetings(root)                      [existing, M01]
        │
        ▼
filter_to_current_meetings(...)          [existing, M03 — REQUIRED here, not optional;
        │                                 see Failure Modes]
        ▼
group_by_statement_kind(...)             [new — single pass, groups by an
        │                                 already-populated field, no
        │                                 re-classification]
        ▼
render_promotion_review(...)             [new — sub-sorts each group by
        │                                 (meeting_date, timestamp), reuses
        │                                 render_statement() per-item]
        ▼
      stdout
```

No write path. No new object creation. No call into anything resembling Vector's
`ingest_transcript.py`/`signal_detection.py` logic — Reader does not re-derive or
second-guess `statement_kind`, it only displays the value Vector already computed and
persisted.

## Complexity

- `group_by_statement_kind`: single pass, `O(n)` — a `dict[str, list]` keyed by
  `statement_kind`, appended to once per Statement. No membership-test-in-a-list
  mistake (the exact class of bug caught and fixed in M03's `linked_meeting_ids`) —
  grouping by a scalar field needs no membership test at all, just a dict key lookup.
- `render_promotion_review`: **not** `O(n)` overall once the Meeting/timestamp ordering
  (decided #4) is included — each group is sorted by `(meeting_date, timestamp)`, i.e.
  `O(g log g)` per group where `g` is that group's size, `O(n log n)` in the worst case
  (one dominant group). Still cheap at real-world scale — 904 real Statements sorted
  well under a millisecond — but this is a genuine, honest correction to the first
  draft's blanket "`O(n)`" claim, which didn't yet account for the ordering decision.
- `filter_to_current_meetings`: `O(n)`, reused unchanged from M03.
- No file I/O beyond the existing `load_statements()`/`load_meetings()` calls, which
  are unchanged from M01/M02/M03 (full-tree `rglob`, already the dominant real cost at
  ~2s for 904 real Statements — not something M04 makes worse or better).

## Compatibility

- **No new Vector field required** for the core classification. `statement_kind` and
  `detected_signals` are both already in `vector-reader-contract.md` v1.0.
- **`meeting_date` is reused, not newly added.** The Meeting-grouping/ordering decision
  (#4) depends on `VectorMeeting.meeting_date` — the same field M03 already introduced
  and flagged as beyond Contract v1.0's stated scope. M04 does not add a *new*
  beyond-contract dependency; it takes on a second consumer of one that already exists.
  Worth stating precisely rather than repeating the first draft's now-inaccurate claim
  that M04 needs "zero" contract extension — it needs zero *new* extension, but does
  inherit M03's existing one.
- **Old-style Statements** with no `statement_kind` at all (checked: none currently
  exist in real `ai/staging/`, since `choose_statement_kind()` has populated every real
  Statement since Vector's own M04, but the field is `Optional[str]` and nothing
  guarantees this stays true for every future or hand-authored Statement) land in a
  separate `unclassified` bucket.
- **Backward compatible** with M01/M02/M03 by construction — this is a new, independent
  module; it doesn't touch `models.py`, `loader.py`, `signals.py`, `query.py`,
  `stats.py`. It reads (but doesn't modify) `navigation.py`'s
  `filter_to_current_meetings`.

## Failure Modes

| Condition | Behavior | Why |
|---|---|---|
| Empty statement list | All six groups render with count 0 | same "always show all groups" discipline as `render_signal_browser`, confirmed as the right default (decided #3) |
| `statement_kind` missing/`None` | Goes to `unclassified` bucket | never silently dropped, never merged into `other` |
| `statement_kind` holds a value outside the 6 known ones (future Vector enum extension) | Goes to its own ad-hoc bucket by that literal value, not an error, not silently dropped into `other` | mirrors the contract's "ignore unknown, don't reject" spirit already used for unknown Statement *fields*; here applied to an unexpected *value* of a known field |
| **`statements` passed in without first calling `filter_to_current_meetings`** | Same Meeting appears as several duplicate sections, once per Vector reindex run | this is not a new failure mode invented for M04 — it is the exact bug M03 found and fixed for Object Navigation; `render_promotion_review` inherits it if a caller skips the filter, which is why the filter is stated as REQUIRED in Public API, not optional |
| A Statement's `meeting_ref` doesn't resolve to any loaded Meeting | Falls into an `(unknown meeting)` sub-section, sorted last within its group | same tolerance policy as `render_mentions`' unresolved-reference handling in M03 — never dropped, never an error |
| Meeting has no `meeting_date` | Sorts after all dated Meetings within the group | same convention `render_entity_timeline` already established |
| A meeting longer than 99 minutes (`timestamp` format is zero-padded `MM:SS`, e.g. `"15:43"`) | Lexicographic string sort of `timestamp` would order incorrectly past 3-digit minutes (`"100:00"` sorts before `"99:59"`) | a real, currently theoretical edge case — checked the longest `timestamp` across every real staged Statement: `32:02` (`MTG-20260727-PKPX`), comfortably 2-digit, but real meetings already run over half an hour, so 99+ minutes is not a remote hypothetical. `render_promotion_review` should parse `timestamp` to seconds (`int(mm)*60+int(ss)`) for the sort key rather than compare the raw string, so this doesn't silently rely on no meeting ever crossing 99 minutes |
| Root path doesn't exist / has no Statements at all | Same as `load_statements()` today — returns `[]`, not an error | unchanged from M01 |

## Vector Contract assumptions

- Relies on `statement_kind` being a single, closed-vocabulary value chosen by Vector's
  own fixed precedence (`metric → question → risk → task → decision → fact`, per
  `signal_detection.choose_statement_kind()`) — Reader treats this as an opaque,
  already-decided classification, never recomputes it (Design Principle).
- Relies on `detected_signals` **only** for display (showing which signals fired
  alongside the `statement_kind` bucket a Statement landed in) — confirmed (decided #2)
  never for grouping or candidate-labeling logic. Vector's own
  `M05_PROMOTION_READINESS.md` signal-combination → label table is explicitly **not**
  reimplemented here — doing so would make Reader a second implementation of Vector's
  business logic, exactly the outcome the Design Principle above exists to prevent.
- Relies on `Meeting.meeting_date` (M03's beyond-contract field) for group ordering —
  an existing dependency, reused, not newly introduced.
- Does **not** assume Vector will ever publish a real Promotion Candidate schema. If it
  does, later, that would be a genuinely new, separate, additive feature (a real
  candidate object Reader could load via `load_objects()`-style code) — not something
  this design blocks on or needs to anticipate structurally.

## Migration

None. No schema change on either side, no data backfill, no reindexing. Purely additive:
a new pure-function module reading fields every real Statement/Meeting already has. Old
and new Reader versions can run side by side against the same Vector data with no
compatibility shim needed, the same way M02 added rendering on top of M01 without
touching stored data.

## Test plan

**Isolated (synthetic fixtures)**, mirroring M02/M03's two-tier pattern:
- Each of the 6 `statement_kind` values buckets correctly; a Statement with `None`
  lands in `unclassified`, not `other`.
- An unexpected `statement_kind` value (simulating a future Vector enum extension) gets
  its own bucket, not merged or dropped.
- All six named groups appear even when every one of them is empty (zero Statements).
- Within a group: Statements from two Meetings with different `meeting_date`s render in
  date order; an undated Meeting's Statements render last; within one Meeting,
  Statements render in `timestamp` order, not load order.
- A Statement whose `meeting_ref` isn't in the given Meetings list renders under
  `(unknown meeting)`, last, not an error.
- Passing statements that were **not** first filtered through
  `filter_to_current_meetings` and confirming the duplicate-Meeting-section symptom
  reproduces on a synthetic supersedes chain (documents the required calling
  convention with a failing-if-skipped test, not just a docstring).
- `render_promotion_review` output format — exact structural assertions, same style as
  `test_render_signal_browser_lists_all_five_groups_even_when_empty`.

**Real data**, against `~/Downloads/Vector` directly (not copied):
- Cross-check `task_signal` count for `MTG-20260727-XMFL` against the number already
  independently confirmed twice in this project's history (M02's `READER_M02.md` cites
  Vector's own `M06_RESULTS.md` reporting `task_signal` count **7** for this exact
  Meeting; verified again while writing this design: `{'task_signal': 7, ...}` out of 98
  real Statements). If `group_by_statement_kind` doesn't reproduce **7**, that's a real
  bug, not a fixture mismatch.
- Full real corpus (`ai/staging/`, run through `filter_to_current_meetings` first, 904
  raw Statements before filtering): distribution checked while writing this design —
  `fact` 472, `other` 175, `metric` 120, `decision_signal` 64, `task_signal` 41,
  `risk_signal` 32, **zero** with `statement_kind` missing. The test should assert the
  six counts sum to the (post-filter) total and that `unclassified` is empty today (a
  currently-true fact about this data, not a structural guarantee — worth asserting
  precisely so a future regression is caught, not assumed away).
- Real Meeting-date ordering: `MTG-20260727-XMFL` has a real `meeting_date` of
  `2026-07-27` (used already in M03's Entity Timeline tests) — confirms the sort key
  resolves correctly against real, not just synthetic, Meeting data.

**Regression**: full `pytest tests/` run, expect 499 → 499 + N passed, zero prior-test
changes required (this module touches nothing M01/M02/M03 already covers, and only
*reads* `filter_to_current_meetings` rather than modifying it).

**Manual CLI smoke test, real data — required, not optional (Standing Principle #4).**
Same sequence M03 actually followed, which is what caught its reindex-duplication bug
before any synthetic fixture did:
- `vector review ~/Downloads/Vector` (whole repo root) — confirm group counts sum
  correctly, confirm no Meeting section appears more than once for a reindexed
  transcript (the exact M03 bug class, now in a new command).
- `vector review ~/Downloads/Vector/ai/staging/MTG-20260727-XMFL` (single meeting root)
  — cross-check its `task_signal` count against the independently-known **7**.
- An empty/nonexistent root — confirm all six groups still render at zero, no traceback.

## Open Questions (decided)

All four resolved before implementation:

1. **Naming.** Decided: `vector review`, not `vector promotion` — Reader reviews, it
   doesn't promote or decide. Reflected in Goal and Public API above.
2. **Scope boundary on "candidate" richness.** Decided: `statement_kind` +
   `detected_signals` only, display-only. Vector's `M05_PROMOTION_READINESS.md`
   signal-combination → label table is explicitly rejected as a Reader-side
   reimplementation — it would make Reader a second implementation of Vector's business
   logic, which is exactly what the new Design Principle exists to prevent. This was
   the most consequential of the four questions and is now also captured as a standing,
   named rule rather than a one-off decision scoped to this milestone.
3. **Show `fact`/`other`/`unclassified` groups?** Decided: yes, always show all groups
   — Reader doesn't hide data; a future `--only task,risk`-style filter is a legitimate
   later addition but explicitly out of scope for M04 itself.
4. **Ordering within a group.** Decided: by Meeting (`meeting_date` order, undated
   last), then by `Statement.timestamp` within a Meeting — natural chronology, matching
   the illustrative example given (`Meeting A: stmt 12, stmt 15` / `Meeting B: stmt 3,
   stmt 9`). This is the one decision that changed the design's complexity and data-flow
   sections materially (sorting, not a single O(n) pass; a new dependency on
   `meeting_date` and, transitively, on `filter_to_current_meetings` to avoid
   reintroducing M03's reindex-duplication bug) — folded into every section above
   rather than left as a footnote.
