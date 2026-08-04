# Reader Release Review — Product Readiness P05

**Status: analysis only. No code, no push, no tag, no GitHub Release created.** Every
item below was re-verified against the real repository state while writing this
(fresh `pytest` run, fresh `git status`/`git log`, fresh checks against Companion's real
data) — not carried over from earlier turns' memory.

---

## 1. Release Checklist

| Item | Status | Evidence |
|---|---|---|
| **Version** | ✅ Present | `pyproject.toml`: `version = "0.2.0"`. Deliberately not `1.0.0` and not a continuation of the orphaned `v1.0.0` tag — rationale in `READER_CHANGELOG_DESIGN.md`. |
| **License** | ✅ Present | `LICENSE` (Apache-2.0) exists; `pyproject.toml`'s `license`/`classifiers` fields set; `pip show ocom-reader` confirms `License: Apache-2.0`, not blank. |
| **CI** | ⚠️ Configured, not yet proven on GitHub | `.github/workflows/tests.yml` exists and was verified locally by simulating exactly what it runs (checkout-equivalent + fresh install + `pytest`: 512 passed). **But it has never actually executed on GitHub** — `git log origin/main..HEAD` shows 6 commits, including the one that added this workflow, still unpushed. A workflow that has never run is configured, not yet demonstrated. |
| **CHANGELOG** | ✅ Present | `CHANGELOG.md` exists, Keep a Changelog format, `## [0.2.0] - 2026-07-27` is the current top entry, includes the "Note on early tags" explaining `v0.1.0`/`v1.0.0`. |
| **README** | ✅ Present, verified | Redesigned in P04; a real clone→install→run experiment was performed and passed (`READER_README_REVIEW.md`). |
| **Documentation** | ✅ Present | `docs/companion-integration.md`, `docs/HISTORY.md`, `docs/architecture/` (46 files), `READER_STATUS.md`, `READER_M01.md`-`READER_M04.md` + design review, `READER_ROADMAP_REVIEW.md`, `READER_PRODUCT_READINESS.md`, `READER_LICENSE_REVIEW.md`, `READER_CI_DESIGN.md`. |
| **Tests** | ✅ Present, verified | **512 passed**, re-run fresh just now, zero failures. |
| **Known limitations** | ✅ Documented | Previously scattered across `READER_STATUS.md`/`docs/companion-integration.md`; consolidated in Section 3 below. |

**The one real gap this checklist surfaces**: everything above is true of the local
repository. **None of it is public yet** — `origin/main` does not have any of the
Companion integration, License, CI, Changelog, or README work. "CI passing" today means
"passing when simulated locally," not "passing on GitHub," because it has had zero
opportunity to run there.

## 2. Release Notes

Draft text for the GitHub Release, tag `v0.2.0`:

---

### OCOM Reader v0.2.0 — First Public Release

Reader's first release backed by an actual changelog, a real license, and automated
testing. Two bodies of work land together: the Companion integration (four milestones,
M01-M04) and a full Product Readiness pass (P01-P04) preparing Reader to be a
genuinely usable, trustworthy open-source project rather than an internal prototype.

**Companion Integration**
- Read Companion's Statement/Meeting/object data per a versioned contract
  (`companion-reader-contract.md` v1.0) — forward/backward compatible by construction.
- Search and browse by signal, independently or combined with speaker/meeting filters.
- Navigate objects: view an object's linked Statements/Meetings/aliases/relationships,
  see what a Statement mentions, cross-meeting views, a relationship tree, a
  chronological timeline.
- A Promotion Review queue, grouping Statements by `statement_kind` for human review —
  deliberately never inventing a richer classification Companion hasn't itself produced.
- 10 new `ocom-reader companion` subcommands in total.

**Product Readiness**
- **License**: Apache License, Version 2.0.
- **CI**: automated test verification on every push/PR (GitHub Actions).
- **Changelog**: `CHANGELOG.md`, Keep a Changelog format, from this release forward.
- **README**: rewritten around a five-minute-test — clone, install, run, point at a
  Companion repository, get a useful result, without needing to open any other document.

**Compatibility**: this release is intended for existing Companion repositories on
Contract v1.0. See "Compatibility" below for the two fields read beyond that
contract's formal scope.

**Known limitations**: see below — none block real use, all are disclosed rather than
discovered later.

Full details: [`CHANGELOG.md`](CHANGELOG.md) · [`READER_STATUS.md`](READER_STATUS.md)
· [`docs/companion-integration.md`](docs/companion-integration.md)

---

## 3. Known Limitations

Consolidated from `READER_STATUS.md` and re-checked directly against Companion's real
data while writing this document, not assumed unchanged:

- **Two fields read beyond Companion Contract v1.0's formal scope**: `Meeting.meeting_date`
  (used for chronological ordering in Entity Timeline and Promotion Review) and the
  common `CompanionObject` schema Object Navigation relies on. Both optional, both
  degrade gracefully to `(none)`/`(date unknown)` if absent — but neither is a
  contractual guarantee yet. See Section 4.
- **`relationships` and `alias:` tags are unpopulated in real Companion data.**
  Re-checked just now: all 6 real objects (`objects/partners/`, `objects/employees/`)
  still have `relationships: []` and zero `alias:` tags. The Relationship Browser and
  Object View's Aliases section are correct and tested (synthetic fixtures), but have
  nothing real to display yet.
- **No real Promotion Candidate data exists in Companion at all** — re-confirmed: no
  schema, no persisted object, nothing beyond Companion's own analysis-only
  `M05_PROMOTION_READINESS.md`. `companion review` groups by `statement_kind` only,
  deliberately, per the binding Design Principle established in M04.
- **Speaker identity is unresolved on Companion's side** — re-confirmed:
  `speaker_resolved: false` on every real Statement checked. `speaker:` search works
  correctly but won't match a real name until Companion resolves this itself.
- **Real Companion data is still narrow**: a single tenant (`companion-primary`) has ever
  been observed; only 2 of Companion's 12 object types (`partners`, `employees`) have any
  real production data. Multi-tenant behavior and most object types are exercised only
  by synthetic fixtures.
- **Runtime dependencies are unpinned** (`pydantic>=2.0`, `pyyaml>=6.0`, no upper
  bound) — a build reproducibility gap flagged in `READER_PRODUCT_READINESS.md`,
  not addressed by this release.
- **CI has never executed on GitHub** (Section 1) — a real gap specific to *this*
  release moment, closed automatically the first time these commits are pushed and a
  workflow run completes, not something requiring further work first.

None of the above are defects discovered late — every one was identified, disclosed,
and in most cases deliberately designed around (not worked around) during the
milestone or Product Readiness item that surfaced it.

## 4. Compatibility

**Reader is compatible with Companion Contract v1.0, plus two explicitly flagged,
temporary extensions beyond it**, not silently assumed stable:

- **Fully covered by Contract v1.0**: `Statement`'s mandatory and optional fields
  (including `detected_signals`, `statement_kind`), and the two `Meeting` fields
  (`source_hash`, `parser_version`) the supersedes chain relies on.
- **Beyond Contract v1.0, read defensively**: `Meeting.meeting_date` and the
  `CompanionObject` common-object schema. Both optional; both documented in
  `docs/companion-integration.md`'s "Supported contract version" section with an explicit
  recommendation that Companion formally address them (a v1.1 addendum, or a second
  contract for the common object schema).
- **Never assumed**: any Companion field or object type not explicitly modeled in
  `companion_integration/models.py` is silently ignored (`extra="ignore"`), not rejected —
  a future Companion field addition cannot break this integration.

## 5. Final Recommendation

**Yes — Reader is ready for a first public release as `0.2.0`, with one concrete,
non-code precondition that has to happen first: pushing these commits.**

Why yes, on the merits: every item in the Release Checklist that's about the actual
codebase — version, license, changelog, README, documentation, and 512 passing tests —
is genuinely done and independently verified in this document and its predecessors
(`READER_PRODUCT_READINESS.md` through `READER_README_REVIEW.md`), not merely
asserted. Known limitations are all disclosed, all bounded, and none of them block a
real user from getting real value today (Signal Explorer, Object Navigation, and
Promotion Review all work against real Companion data right now; only the Relationship
Browser and Aliases display have nothing real to show yet, and that's a Companion-data
gap, not a Reader defect).

**The one thing that genuinely blocks calling this "released" is not a code or
documentation gap — it's that none of this is public yet.** `origin/main` is 6
commits behind local `main`. A release requires:
1. Pushing these commits to `origin`.
2. Confirming the CI workflow actually runs and passes on GitHub (closing the one
   "configured but not proven" item in Section 1).
3. Creating an annotated tag `v0.2.0` — a new, disciplined tag, deliberately not
   reusing or continuing the orphaned `v1.0.0`.
4. Publishing the GitHub Release using the text in Section 2.

**None of these four are done in this document, and none should be done without your
explicit go-ahead** — pushing to a remote and publishing a public release are exactly
the kind of visible, not-easily-reversed actions this project's own established
discipline (confirm before acting) applies to. This review answers "is the project
ready," not "push it" — that's a separate decision for you to make.
