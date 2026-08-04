# Reader 0.2 Retrospective

**Written at the close of this development cycle, deliberately before opening any new
milestone.** `v0.2.0`'s commits (`f4584fc` through `263c977`, 8 total) are pushed to
`origin/main`; 512 tests pass. This document is the boundary marker between "building
the first real product" and whatever comes next — not a plan for what's next, which is
exactly the point: that decision belongs to a fresh cycle, not to momentum from this
one.

## What M01-M04 achieved

Reader went from zero Companion integration to a full, tested, read-only client in four
milestones: reading Statement/Meeting data against a versioned contract (M01), signal
search and browsing (M02), object navigation — views, reverse mentions, cross-meeting
tracking, a relationship browser, a timeline (M03) — and a Promotion Review queue
(M04). Ten `companion` CLI subcommands, all read-only, all exercised against Companion's
actual repository throughout, not only synthetic fixtures.

The harder win wasn't the feature count — it was holding a line under real temptation
to cross it. M04's design review found that Companion has no persisted Promotion
Candidate data at all; the obvious shortcut was to replicate Companion's own analysis-only
signal-combination table inside Reader and ship something that *looked* more capable.
That was rejected, in writing, before any code existed, and the rejection became a
standing rule (M04's Design Principle) rather than a one-off call. Two real bugs were
caught specifically because of the discipline of running things against real data
before calling them done, not because they were anticipated in design: M03's
reindex-duplication bug (a single real meeting counted six times), found by actually
running the CLI against the full repository, not just a scoped test directory; and a
wrong guess in M04's own design doc about real meeting lengths, caught by checking
before shipping instead of after.

## What P01-P05 did

Five Product Readiness items turned a tested-but-unreleasable prototype into something
actually publishable: a license chosen for reasons specific to what Reader actually is
(P01), CI that was rehearsed locally before being trusted (P02), a changelog and
version number that resolved a real, previously-invisible inconsistency instead of
papering over it (P03), a README that was verified by actually attempting the
onboarding path it promises, not just proofread (P04), and a release review that named
the one thing still not true ("nothing is public yet") instead of declaring victory
early (P05) — followed by actually pushing once that gap was named.

## Which decisions turned out well

- **Design review before code, every time it mattered.** M04's design doc caught the
  Promotion Candidate non-existence problem *before* a line of promotion logic was
  written. P03's changelog design surfaced the `v1.0.0` tag's internal contradiction
  before a version number was chosen, not after. Neither of these was free — both
  added a full analysis pass before implementation — but neither produced rework
  either, which is the actual test of whether the discipline paid for itself.
- **Grounding claims in real data instead of reasoning from the design.** Every time
  this was skipped even slightly — a guess about typical meeting length, an assumption
  that a scoped test directory represented the whole repository — it was wrong. Every
  time a claim was checked against `~/Downloads/Companion` directly before being written
  down, it held up. The pattern is consistent enough across eight milestones to trust
  as a rule, not a coincidence.
- **Refusing the generic default when a specific answer was better-grounded.** MIT
  would have been the defensible, low-effort license choice. Apache-2.0 was chosen
  instead because Reader is specifically a reference implementation of a
  specification that is itself Apache-2.0, with a plugin ecosystem already built —
  a conclusion that required checking a sibling repository's license, not something a
  generic checklist would have surfaced.
- **Stabilizing before adding.** The roadmap review (before P01) concluded a new
  milestone wasn't the right next step — Product Readiness was. That's an easy
  conclusion to state and a harder one to actually act on instead of defaulting to
  "more features." Five items later, it held.
- **Isolated, single-purpose commits.** Every Product Readiness item landed as its own
  commit, closeable and revertable independently. Nothing in this cycle required
  going back to untangle what belonged to which change.

## What was consciously deferred, and to what

Two different categories, worth keeping distinct rather than lumping together as one
undifferentiated "future work" pile:

**Deferred by Reader's own choice** — things Reader could build now but chose not to,
on purpose:
- Full-text search over `Statement.text` and wiring `companion` into the existing
  multi-repo workspace mechanism — both identified as real, buildable, low-risk gaps
  (`READER_ROADMAP_REVIEW.md`), deliberately left for a future cycle rather than
  bundled into this one.
- A richer Promotion Candidate classification (beyond `statement_kind` alone) — not a
  gap to close later so much as a boundary to keep permanently, unless Companion itself
  ever publishes real candidate data. This one isn't "not yet"; it's "not Reader's to
  build."
- Dependency version pinning, a documentation index for `docs/architecture/`'s 46
  files, and per-file license headers — real, minor, explicitly named, not urgent.

**Deferred because they're blocked on Companion, not on Reader** — no amount of future
Reader work closes these on its own:
- `meeting_date` and the `CompanionObject` schema remain outside Companion's formal contract,
  flagged in every document that depends on them since M03, still unresolved on
  Companion's side.
- `relationships` and `alias:` tags are unpopulated in every real Companion object that
  exists today — the Relationship Browser and Aliases display are correct and tested,
  with nothing real yet to point them at.
- Speaker identity resolution doesn't exist in Companion yet, so `speaker:` search can't
  match a real name no matter what Reader does.
- Real Companion data is still one tenant, five current meetings, two of twelve object
  types populated — not a defect, just where things actually are right now.

None of these were discovered late. Every one was named, in writing, at the moment it
became relevant, and none of them blocked `v0.2.0` from being real, tested, and
useful today.
