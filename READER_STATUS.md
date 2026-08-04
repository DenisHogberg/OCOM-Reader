# Reader Status — Companion Integration

**Entry point for anyone new to this project.** Read this first, before the individual
milestone reports (`READER_M01.md` … `READER_M04.md`) or the design review
(`READER_M04_DESIGN.md`) — those explain *how* each capability was built and verified;
this explains *what currently exists* and *what it depends on*. Everything below is
checked against the actual repository state as of this writing (test counts, real CLI
output), not recalled from memory.

## Implemented

- ✓ **M01 — Contract Compliance** (`READER_M01.md`) — reads Companion's Statement/Meeting
  objects per `docs/contracts/companion-reader-contract.md` v1.0; forward/backward
  compatible by construction (`extra="ignore"`, optional fields default safely).
- ✓ **M02 — Signal Explorer** (`READER_M02.md`) — Meeting Summary, Signal Browser, full
  Signal View, combinable `signal:`/`speaker:`/`meeting:` search, global stats.
- ✓ **M03 — Object Navigation** (`READER_M03.md`) — Object View, reverse navigation
  (Mentions), Cross-Meeting View, a text-only Relationship Browser, Entity Timeline.
- ✓ **M04 — Promotion Review UI** (`READER_M04.md`, design reviewed in
  `READER_M04_DESIGN.md`) — Statements grouped by `statement_kind` for human review;
  Reader classifies nothing itself.

## Current capabilities (CLI: `ocom-reader companion <command>`)

| Command | What it does | From |
|---|---|---|
| `show <path> [--root]` | One Statement's full Signal View; `--root` adds a Mentions block | M01/M02/M03 |
| `search <root> [query \| --signal]` | Combinable `signal:`/`speaker:`/`meeting:` filter | M01/M02 |
| `signals <root>` | Signal Browser — every Statement grouped by signal | M02 |
| `summary <root>` | Meeting Summary — signal counts, multi-/zero-signal rates | M02 |
| `stats <root>` | Global Meeting/Statement/signal counts | M02 |
| `object <root> <id>` | Object View — type, name, linked Statements/Meetings, aliases, relationships | M03 |
| `mentioned-in <root> <id>` | Cross-Meeting View | M03 |
| `relationships <root> <id>` | Relationship Browser — plain text tree | M03 |
| `timeline <root> <id>` | Entity Timeline — mentions by Meeting, date-ordered | M03 |
| `review <root>` | Promotion Review — Statements grouped by `statement_kind` | M04 |

Implementation: `src/ocom_reader/companion_integration/` (`models.py`, `loader.py`,
`signals.py`, `query.py`, `stats.py`, `navigation.py`, `promotion.py`). Tests:
`tests/test_companion_integration.py` — **512 passing** as of M04 (all against both
synthetic fixtures and Companion's real, live repository at `~/Downloads/Companion`, not
copies).

## Contract dependencies

- **Contract v1.0** (`docs/contracts/companion-reader-contract.md`) — the formal,
  versioned API: Statement's mandatory/optional fields, plus two Meeting fields
  (`source_hash`, `parser_version`) for the supersedes chain. Fully covered.
- **`Meeting.meeting_date`** *(temporary — beyond Contract v1.0)* — introduced in M03
  for Entity Timeline, reused in M04 for Promotion Review's ordering. No Statement-level
  contracted field substitutes for it. Needs either a formal v1.1 addendum or Companion
  telling Reader to source the date another way.
- **`CompanionObject`** *(temporary — beyond Contract v1.0)* — Companion's common
  non-Statement/Meeting object frontmatter (Partner/Company/Employee/Task/Decision/
  Risk/Issue/Document/Project/Product/Evidence), introduced in M03. No contract for this
  shape exists yet, only Companion's own internal `docs/object-model.md`.

Both exceptions are read defensively (optional, tolerant of absence) and are restated
in `docs/companion-integration.md` on every milestone that depends on them — not something
that quietly became "assumed stable."

## Known limitations

- **`relationships` not populated.** All 6 real Companion objects (`PTN-*`, `EMP-*`) have
  an empty `relationships` list today — checked directly, not assumed. The Relationship
  Browser is correct and tested (synthetic fixtures), but has nothing real to walk yet.
- **`alias:` tags not populated.** Same 6 real objects have no `alias:` tags. Object
  View's Aliases section is correct but shows `(none)` against real data today.
- **Promotion Candidate data is absent in Companion entirely.** No schema, no persisted
  object, no field — checked directly (`find`/`grep` across Companion's repo) before M04's
  design. Companion's own `M05_PROMOTION_READINESS.md` is analysis-only ("no objects
  created, no pipeline code changed"). M04's Promotion Review works around this by
  grouping on the one real, already-contracted field (`statement_kind`) instead of
  waiting on data that doesn't exist yet.
- **Speaker identity not resolved.** Every Statement's `speaker` field is Companion's raw
  diarization label (`"Speaker 1"`, `"Speaker 2"`) in all real data observed — searching
  `speaker:Denis` finds nothing until Companion resolves speaker identity on its side. A
  Companion-side gap Reader inherits, not something Reader can work around.

## Design rules (standing, not milestone-scoped)

Confirmed by the user during M04's design review as binding for every future
milestone, not just M04 — see `READER_M04_DESIGN.md`'s "Standing Principles":

1. **No new contract fields.** Reader consumes only what the contract already
   publishes, or an already-flagged beyond-contract exception (never a field proposed
   for a Reader feature's convenience).
2. **Reader is read-only.** No write-back into Companion, no exceptions.
3. **No hidden heuristics.** If a grouping needs a guess Reader can't ground in an
   exact, already-published field value, show the raw data instead of inventing a
   classification.
4. **Testing discipline, in order:** unit tests → full regression suite → manual CLI
   smoke test against the real `~/Downloads/Companion` repository. Not optional — this
   sequence is what caught M03's real reindex-duplication bug, which no synthetic
   fixture surfaced.
5. **Document every contract discrepancy** until Companion formally closes it.

And the sharpest form of the rule, from M04's Design Principle:

> Reader MUST NOT infer new semantic objects. Reader MAY group, sort, and visualize
> contracted Companion data. Reader MUST NOT create Promotion Candidates, Promotion
> Scores, Promotion Labels, or any derived workflow state absent from the Companion
> Contract.

## What's next (not started, not designed)

No M05 has been scoped or design-reviewed yet. Per the standing principles above, any
future milestone touching `companion_integration/` should get a `READER_M0X_DESIGN.md`
first (Goal / Public API / Data Flow / Complexity / Compatibility / Failure Modes /
Companion Contract assumptions / Migration / Test plan / Open Questions), the same way M04
did, before any code is written.
