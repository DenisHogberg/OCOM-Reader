# Vector Integration

Reader's implementation of `docs/contracts/vector-reader-contract.md`, published by the
Vector repository. Covers Reader M01 (Contract Compliance, `READER_M01.md`), M02
(Signal Explorer, `READER_M02.md`), M03 (Object Navigation, `READER_M03.md`), and M04
(Promotion Review UI, `READER_M04.md`, design reviewed in `READER_M04_DESIGN.md`).
Implementation lives in `src/ocom_reader/vector_integration/`; tests in
`tests/test_vector_integration.py`.

## Supported contract version

**Contract Version 1.0** (Vector `PARSER_VERSION 1.4.0`). Reader tracks this version
explicitly in this document, not in code — there is no runtime version negotiation; if
Vector publishes a Contract Version 2.0 with breaking changes, this document (and
`vector_integration/models.py`) need a corresponding update, not an automatic adaptation.

**Reader M03 (Object Navigation) reads beyond Contract v1.0's stated scope.** The
contract governs only Statement fields (plus two Meeting fields for the supersedes
chain). M03 needed two things it does not cover, and both are called out explicitly
rather than silently assumed stable:

- **`VectorObject`** (`vector_integration/models.py`) — Vector's *common* object
  frontmatter (id/type/title/tenant/owner/status/lifecycle/confidence/source/
  relationships/references/evidence/tags), shared by Partner/Company/Employee/Task/
  Decision/Risk/Issue/Document/Project/Product/Evidence per Vector's own
  `docs/object-model.md`. No contract for this shape exists yet — only Vector's own
  (non-versioned) internal documentation. **Recommendation for Vector**: publish a
  second contract (or a v1.1 addendum to this one) covering the common object schema,
  the same way Statement's fields are covered today.
- **`Meeting.meeting_date`** — an optional field Entity Timeline needs for chronological
  sorting; no Statement-level field the contract already covers substitutes for it
  (`Statement.created` is Reader's ingestion date, not the meeting's date;
  `Statement.timestamp` is only an offset within the recording). Read, but not
  contractually guaranteed — Vector should confirm this as a deliberate, documented
  addition or tell Reader to source the date another way.

Both are optional/tolerant of absence — a Vector object or Meeting missing them still
loads and renders (Aliases/Relationships as "(none)"; Timeline entries as
"(date unknown)"), never an error.

**Reader M04 (Promotion Review UI) reuses `Meeting.meeting_date`, introduces nothing
new.** Promotion Review orders each `statement_kind` group's Statements by Meeting (date
order, undated last), which depends on the same beyond-contract `meeting_date` field M03
introduced — a second consumer of an existing exception, not a new one. M04 adds zero
new fields beyond that.

## Compatibility

- **Backward**: Statement objects predating Vector's `detected_signals` field (before
  Vector's own `PARSER_VERSION 1.3.0`) load exactly as well as ones with it —
  `detected_signals` defaults to an empty list, never `None`, never an error.
- **Forward**: any field on a Statement or Meeting that Reader doesn't yet model is
  silently ignored (`ConfigDict(extra="ignore")` on both `VectorStatement` and
  `VectorMeeting`) — a future Vector field never breaks this integration.
- **Mixed data**: old-style and new-style Statements load together from the same
  directory tree without special-casing — verified directly against Vector's real
  `ai/staging/` tree, which genuinely contains both (see `READER_M01.md`).
- Every guarantee above is exercised against Vector's actual, real, already-ingested data
  at `~/Downloads/Vector` in `tests/test_vector_integration.py` — not only synthetic
  fixtures.

## What Reader does NOT do

- **Does not write back into a Vector repository.** Everything here is read-only. Reader
  has no role in Vector's write-back governance (Vector's `docs/ai-collaboration.md`).
- **Does not resolve speaker identity.** Every Statement's `speaker` field is Vector's raw
  diarization label (e.g. `"Speaker 1"`) in all real data observed so far —
  `speaker_resolved` is `False` throughout. `speaker:` search filters against this raw
  label; searching `speaker:Denis` will find nothing until Vector's own identity
  resolution for speakers exists and populates real names into that field. This is a
  Vector-side limitation Reader inherits, not something Reader can work around.
- **Does not hard-code a `detected_signals` combination → meaning table.** Per the
  contract's own explicit requirement: the five-signal vocabulary (`metric`, `question`,
  `risk`, `task`, `decision`) is stable, but which combinations of them appear is not
  closed and keeps growing as Vector ingests more transcripts. Every function in
  `vector_integration/signals.py` and `query.py` reasons about one signal at a time.
- **Query DSL (M02) supports one value per filter key per query.** `signal:task
  speaker:Denis meeting:XMFL` combines three *different* keys; `signal:task
  signal:risk` (the same key twice) raises an error rather than silently picking one —
  a stated M02 scope limit, not an oversight (see `vector_integration/query.py`'s
  docstring). A filter value containing a space isn't representable either, for the same
  whitespace-splitting reason.
- **Not integrated into Reader's own `ask`/`search`/`explain`/`Reader` facade.** The
  `vector` subcommand is fully independent of Reader's `--repo`/workspace machinery — a
  Vector repository is a separate external input, not "the repository being read" the way
  Pipeline A's `RetrievalEngine` means it. Whether/how to unify these is left to a later
  milestone.
- **No promotion, no object creation of any kind.** Reader only displays and searches
  what Vector has already produced.
- **Promotion Review (M04) does not classify or score anything itself.** It groups
  Statements by the single, already-decided `statement_kind` field Vector already
  computed and persisted — never by a `detected_signals` combination. Vector's own
  `M05_PROMOTION_READINESS.md` (Vector-side numbering) contains a signal-combination →
  candidate-label table; that table is **deliberately not reimplemented** on Reader's
  side, because doing so would make Reader a second implementation of Vector's business
  logic. See `READER_M04_DESIGN.md`'s "Design Principle": *Reader MUST NOT infer new
  semantic objects; Reader MAY group, sort, and visualize contracted Vector data; Reader
  MUST NOT create Promotion Candidates, Promotion Scores, Promotion Labels, or any
  derived workflow state absent from the Vector Contract.* This is a standing rule for
  every future milestone, not a one-off decision scoped to M04.
- **Object Navigation (M03) has no real `relationships` or `alias:` tags to show yet.**
  Checked directly against Vector's real data: all 6 real Partner/Employee objects have
  empty `relationships`, `references`, `evidence`, and no `alias:` tags. Object View's
  Aliases/Relationships sections and the Relationship Browser are correct and tested
  (against synthetic fixtures), but have nothing to display against real data today —
  an honest gap in the data, not in the Reader-side implementation.
- **Entity Timeline is a timeline of mentions, not of field-level changes.** Reader reads
  one current snapshot of each object file, not Vector's git history, so it has no way to
  know what an object's fields looked like at an earlier point in time. "Mentioned in a
  meeting on this date" is not the same claim as "the object's data changed on this
  date" — only the former is shown.
- **Object Navigation collapses Vector's reindex chains to the current run.** Vector's
  M03 (Source Identity) reprocesses the same real meeting multiple times as its pipeline
  improves (same `source_hash`, different `parser_version`), leaving several superseded
  Meeting objects with the same title sitting side by side in `ai/staging/`. Without
  correcting for this, an object's Linked Statements/Meetings/Cross-Meeting View/Timeline
  would over-count by however many times that meeting was reprocessed — discovered by
  actually running these commands against Vector's real repository root (Angelina showed
  up "mentioned in" the same meeting title 6 times before this fix). `object`,
  `mentioned-in`, and `timeline` all filter Statements down to only those belonging to a
  non-superseded ("current") Meeting first, via the same `find_current_meetings()`/
  `supersedes` resolution Vector's own pipeline uses
  (`vector_integration/navigation.filter_to_current_meetings`). Reverse navigation
  (`show --root`, Mentions for one already-selected Statement) is unaffected, since it
  never aggregates across meetings.

## CLI examples

```bash
# Full Signal View for one Statement — Speaker, Kind, Detected Signals, Text.
ocom-reader vector show path/to/STM-20260727-2GQ5--statement.md

# Meeting Summary — signal counts + multi-/zero-signal rates for one Meeting.
ocom-reader vector summary path/to/vector-repo/ai/staging/MTG-20260727-XMFL

# Signal Browser — every Statement grouped by signal (all five groups always shown).
ocom-reader vector signals path/to/vector-repo/ai/staging/MTG-20260727-XMFL

# Search — M01-compatible single-signal shorthand:
ocom-reader vector search path/to/vector-repo/ai/staging --signal task

# Search — M02 combinable query (any subset of signal:/speaker:/meeting:, ANDed):
ocom-reader vector search path/to/vector-repo/ai/staging "signal:risk meeting:XMFL"
ocom-reader vector search path/to/vector-repo/ai/staging "signal:task speaker:Denis"

# Global statistics across every Meeting/Statement under a path.
ocom-reader vector stats path/to/vector-repo/ai/staging

# Object View — type, name, linked Statement/Meeting counts, aliases, relationships.
ocom-reader vector object path/to/vector-repo PTN-20260727-A1NG

# Reverse Navigation — add --root to `show` to also print the Mentions block
# (the objects this Statement's `references` resolve to).
ocom-reader vector show path/to/STM-....md --root path/to/vector-repo

# Cross-Meeting View — every (non-superseded) Meeting this object is mentioned in.
ocom-reader vector mentioned-in path/to/vector-repo PTN-20260727-A1NG

# Relationship Browser — a plain text tree walk of this object's typed relationships.
ocom-reader vector relationships path/to/vector-repo PTN-20260727-A1NG

# Entity Timeline — mentions grouped by Meeting, sorted by meeting_date.
ocom-reader vector timeline path/to/vector-repo PTN-20260727-A1NG

# Promotion Review — every Statement grouped by statement_kind (all seven
# groups always shown), sub-sectioned by Meeting (date order), then by
# Statement.timestamp within a Meeting. Reader only displays; it never
# classifies, scores, or decides.
ocom-reader vector review path/to/vector-repo/ai/staging
```

`root`/`path` arguments accept either a single Meeting's staging directory
(`ai/staging/<meeting-id>/`) or a whole tree (`ai/staging/` or `objects/`) — every command
recurses.
