# Companion Integration

Reader's implementation of `docs/contracts/companion-reader-contract.md`, published by the
Companion repository. Covers Reader M01 (Contract Compliance, `READER_M01.md`), M02
(Signal Explorer, `READER_M02.md`), M03 (Object Navigation, `READER_M03.md`), and M04
(Promotion Review UI, `READER_M04.md`, design reviewed in `READER_M04_DESIGN.md`).
Implementation lives in `src/ocom_reader/companion_integration/`; tests in
`tests/test_companion_integration.py`.

## Supported contract version

**Contract Version 1.1** (Companion `PARSER_VERSION 1.4.0`). Reader tracks this version
explicitly in this document, not in code — there is no runtime version negotiation; if
Companion publishes a Contract Version 2.0 with breaking changes, this document (and
`companion_integration/models.py`) need a corresponding update, not an automatic adaptation.

**Reader M03 (Object Navigation) reads fields Contract v1.1 now formally covers.**
Contract v1.0 governed Statement only; M03 needed two things it didn't cover at the
time, called out explicitly as a "beyond contract" exception rather than silently
assumed stable. Both are now formally part of the contract as of v1.1 — nothing about
Reader's own code changed to make this true, since both fields already behaved exactly
as documented; this is Companion's contract catching up to already-verified reality:

- **`CompanionObject`** (`companion_integration/models.py`) — the 13-field common object
  subset (`id`/`type`/`title`/`tenant`/`owner`/`status`/`lifecycle`/`confidence`/
  `source`/`relationships`/`references`/`evidence`/`tags`) shared by Partner/Company/
  Employee/Task/Decision/Risk/Issue/Document/Project/Product/Evidence, now the
  "Common Object Schema" section of `companion-reader-contract.md`. Note this is
  deliberately the subset Reader actually reads, not Companion's full common schema —
  `domain`/`language`/`created`/`updated` remain outside the contract, since
  `CompanionObject` doesn't model any of them today.
- **`Meeting.meeting_date`** — an optional field Entity Timeline needs for
  chronological sorting; no Statement-level field the contract already covers
  substitutes for it (`Statement.created` is Reader's ingestion date, not the
  meeting's date; `Statement.timestamp` is only an offset within the recording). Now
  part of the contract's "Meeting" section, alongside `parser_version` and the
  `supersedes` relationship (which M03 already depended on before v1.1, via
  Statement's own guarantees).

Both remain optional/tolerant of absence — a Companion object or Meeting missing them
still loads and renders (Aliases/Relationships as "(none)"; Timeline entries as
"(date unknown)"), never an error.

**Reader M04 (Promotion Review UI) reuses `Meeting.meeting_date`, introduces nothing
new.** Promotion Review orders each `statement_kind` group's Statements by Meeting (date
order, undated last), which depends on the same `meeting_date` field M03 introduced —
now contracted, not an exception. M04 adds zero new fields beyond that.

## Compatibility

- **Backward**: Statement objects predating Companion's `detected_signals` field (before
  Companion's own `PARSER_VERSION 1.3.0`) load exactly as well as ones with it —
  `detected_signals` defaults to an empty list, never `None`, never an error.
- **Forward**: any field on a Statement or Meeting that Reader doesn't yet model is
  silently ignored (`ConfigDict(extra="ignore")` on both `CompanionStatement` and
  `CompanionMeeting`) — a future Companion field never breaks this integration.
- **Mixed data**: old-style and new-style Statements load together from the same
  directory tree without special-casing — verified directly against Companion's real
  `ai/staging/` tree, which genuinely contains both (see `READER_M01.md`).
- Every guarantee above is exercised against Companion's actual, real, already-ingested data
  at `~/Downloads/Companion` in `tests/test_companion_integration.py` — not only synthetic
  fixtures.

## What Reader does NOT do

- **Does not write back into a Companion repository.** Everything here is read-only. Reader
  has no role in Companion's write-back governance (Companion's `docs/ai-collaboration.md`).
- **Does not resolve speaker identity.** Every Statement's `speaker` field is Companion's raw
  diarization label (e.g. `"Speaker 1"`) in all real data observed so far —
  `speaker_resolved` is `False` throughout. `speaker:` search filters against this raw
  label; searching `speaker:Denis` will find nothing until Companion's own identity
  resolution for speakers exists and populates real names into that field. This is a
  Companion-side limitation Reader inherits, not something Reader can work around.
- **Does not hard-code a `detected_signals` combination → meaning table.** Per the
  contract's own explicit requirement: the five-signal vocabulary (`metric`, `question`,
  `risk`, `task`, `decision`) is stable, but which combinations of them appear is not
  closed and keeps growing as Companion ingests more transcripts. Every function in
  `companion_integration/signals.py` and `query.py` reasons about one signal at a time.
- **Query DSL (M02) supports one value per filter key per query.** `signal:task
  speaker:Denis meeting:XMFL` combines three *different* keys; `signal:task
  signal:risk` (the same key twice) raises an error rather than silently picking one —
  a stated M02 scope limit, not an oversight (see `companion_integration/query.py`'s
  docstring). A filter value containing a space isn't representable either, for the same
  whitespace-splitting reason.
- **Not integrated into Reader's own `ask`/`search`/`explain`/`Reader` facade.** The
  `companion` subcommand is fully independent of Reader's `--repo`/workspace machinery — a
  Companion repository is a separate external input, not "the repository being read" the way
  Pipeline A's `RetrievalEngine` means it. Whether/how to unify these is left to a later
  milestone.
- **No promotion, no object creation of any kind.** Reader only displays and searches
  what Companion has already produced.
- **Promotion Review (M04) does not classify or score anything itself.** It groups
  Statements by the single, already-decided `statement_kind` field Companion already
  computed and persisted — never by a `detected_signals` combination. Companion's own
  `M05_PROMOTION_READINESS.md` (Companion-side numbering) contains a signal-combination →
  candidate-label table; that table is **deliberately not reimplemented** on Reader's
  side, because doing so would make Reader a second implementation of Companion's business
  logic. See `READER_M04_DESIGN.md`'s "Design Principle": *Reader MUST NOT infer new
  semantic objects; Reader MAY group, sort, and visualize contracted Companion data; Reader
  MUST NOT create Promotion Candidates, Promotion Scores, Promotion Labels, or any
  derived workflow state absent from the Companion Contract.* This is a standing rule for
  every future milestone, not a one-off decision scoped to M04.
- **Object Navigation (M03) has no real `relationships` or `alias:` tags to show yet.**
  Checked directly against Companion's real data: all 6 real Partner/Employee objects have
  empty `relationships`, `references`, and no `alias:` tags. Object View's
  Aliases/Relationships sections and the Relationship Browser are correct and tested
  (against synthetic fixtures), but have nothing to display against real data today —
  an honest gap in the data, not in the Reader-side implementation. `evidence` is the
  exception: Companion's Phase 3.1 (PR-2) populated real `evidence:` references on all 6,
  which Object View's Evidence section (Reader M05) does display against real data —
  see below.
- **Object View's Evidence section (Reader M05) is frontmatter-only — it does not read
  or render the Evidence object's Markdown body.** It shows `source_type` and the
  Evidence object's id for each resolved `evidence:` entry, resolved the same way
  Reverse Navigation resolves `references` — nothing new. It deliberately does **not**
  parse the `## Excerpt` section of an Evidence object's body; that would require the
  loader to read Markdown bodies at all, which it doesn't do anywhere today, and was
  scoped out of this milestone as a separate, later architectural decision if the
  excerpt text turns out to be worth showing.
- **Entity Timeline is a timeline of mentions, not of field-level changes.** Reader reads
  one current snapshot of each object file, not Companion's git history, so it has no way to
  know what an object's fields looked like at an earlier point in time. "Mentioned in a
  meeting on this date" is not the same claim as "the object's data changed on this
  date" — only the former is shown.
- **Object Navigation collapses Companion's reindex chains to the current run.** Companion's
  M03 (Source Identity) reprocesses the same real meeting multiple times as its pipeline
  improves (same `source_hash`, different `parser_version`), leaving several superseded
  Meeting objects with the same title sitting side by side in `ai/staging/`. Without
  correcting for this, an object's Linked Statements/Meetings/Cross-Meeting View/Timeline
  would over-count by however many times that meeting was reprocessed — discovered by
  actually running these commands against Companion's real repository root (Jordan showed
  up "mentioned in" the same meeting title 6 times before this fix). `object`,
  `mentioned-in`, and `timeline` all filter Statements down to only those belonging to a
  non-superseded ("current") Meeting first, via the same `find_current_meetings()`/
  `supersedes` resolution Companion's own pipeline uses
  (`companion_integration/navigation.filter_to_current_meetings`). Reverse navigation
  (`show --root`, Mentions for one already-selected Statement) is unaffected, since it
  never aggregates across meetings.

## CLI examples

```bash
# Full Signal View for one Statement — Speaker, Kind, Detected Signals, Text.
ocom-reader companion show path/to/STM-00000000-DEMO--statement.md

# Meeting Summary — signal counts + multi-/zero-signal rates for one Meeting.
ocom-reader companion summary path/to/companion-repo/ai/staging/MTG-00000000-DEMO

# Signal Browser — every Statement grouped by signal (all five groups always shown).
ocom-reader companion signals path/to/companion-repo/ai/staging/MTG-00000000-DEMO

# Search — M01-compatible single-signal shorthand:
ocom-reader companion search path/to/companion-repo/ai/staging --signal task

# Search — M02 combinable query (any subset of signal:/speaker:/meeting:, ANDed):
ocom-reader companion search path/to/companion-repo/ai/staging "signal:risk meeting:XMFL"
ocom-reader companion search path/to/companion-repo/ai/staging "signal:task speaker:Denis"

# Global statistics across every Meeting/Statement under a path.
ocom-reader companion stats path/to/companion-repo/ai/staging

# Object View — type, name, linked Statement/Meeting counts, aliases, relationships,
# evidence (source_type + id per resolved entry — frontmatter only, no excerpt text).
ocom-reader companion object path/to/companion-repo PTN-00000000-DEMO

# Reverse Navigation — add --root to `show` to also print the Mentions block
# (the objects this Statement's `references` resolve to).
ocom-reader companion show path/to/STM-....md --root path/to/companion-repo

# Cross-Meeting View — every (non-superseded) Meeting this object is mentioned in.
ocom-reader companion mentioned-in path/to/companion-repo PTN-00000000-DEMO

# Relationship Browser — a plain text tree walk of this object's typed relationships.
ocom-reader companion relationships path/to/companion-repo PTN-00000000-DEMO

# Entity Timeline — mentions grouped by Meeting, sorted by meeting_date.
ocom-reader companion timeline path/to/companion-repo PTN-00000000-DEMO

# Promotion Review — every Statement grouped by statement_kind (all seven
# groups always shown), sub-sectioned by Meeting (date order), then by
# Statement.timestamp within a Meeting. Reader only displays; it never
# classifies, scores, or decides.
ocom-reader companion review path/to/companion-repo/ai/staging
```

`root`/`path` arguments accept either a single Meeting's staging directory
(`ai/staging/<meeting-id>/`) or a whole tree (`ai/staging/` or `objects/`) — every command
recurses.
