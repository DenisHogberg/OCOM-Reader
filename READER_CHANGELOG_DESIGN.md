# Reader Changelog & Versioning Design — Product Readiness P03

**Status: analysis only, Stage 1. No CHANGELOG.md added, no version number changed.**
Per this task's own two-stage structure, Stage 2 (implementation) happens only after
this analysis is reviewed and confirmed — unlike P01/P02, where the requested outcome
was already decisive or fully specified. The Recommendation in Section 5 is a genuine
strategic call (what version number the project starts truly disciplined
versioning at) with real downstream consequences, not a mechanical choice — exactly
the kind of decision this project's own established discipline treats as the user's to
make. Every claim below was checked directly against `git log`, `git tag`,
`git ls-remote`, and `git show`, not recalled.

---

## 1. Version Review

### Why does tag `v1.0.0` exist while the project version is `0.1.0`?

Checked directly, not assumed — the full, real picture:

- `pyproject.toml`'s `version` field has read `"0.1.0"` since the very first commit
  that introduced the file (`fc5c40e`, "feat: complete first OCOM Reader pipeline and
  consistency test") and has **never changed since**, across the entire git history.
- Two tags exist, both already pushed to `origin` (`git ls-remote --tags origin`
  confirms both are public, not local-only): `v0.1.0` (annotated, message "OCOM v0.1.0
  Architecture Foundation") and `v1.0.0` (**lightweight** — `git cat-file -t v1.0.0`
  returns `commit`, not `tag`; no annotation, no message of its own).
- Both tags were cut **the same day**, 2.5 hours apart (2026-07-23, 13:12 and 15:42).
- The commit `v1.0.0` actually points to is titled **"docs: freeze OCOM Runtime v0.2
  reliability milestone"** — the tag says `v1.0.0`; the commit message it points to
  says `v0.2`. The tag name and its own commit's stated version disagree with each
  other.
- Both tags were cut **before** `ab6e972` — "feat: complete OCOM Reader MVP" — the
  commit that finished M006-M010, the CLI-facing `ask`/`search`/`explain`/`related`
  pipeline most people would recognize as "Reader" today. In other words: `v1.0.0` was
  tagged before the product this repository ships today had even reached a first
  complete, usable state.

**Conclusion**: `v0.1.0` and `v1.0.0` are not a disciplined release history for the
`ocom-reader` package. They read as narrative milestone markers for an earlier,
exploratory arc of work described in "OCOM"/"OCOM Agent"/"OCOM Runtime" language
(`c55d0ba` "freeze OCOM Reader v0.1 architecture foundation", `dc673c1` "define OCOM
Agent v0.1 architecture design", `20a2196` "implement OCOM end-to-end reasoning path
v0.1") — a track that used semver-shaped tag names loosely, disagreed with its own
commit messages, and was abandoned (zero tags since, across 15 further substantial
commits including the entire Reader MVP, extensibility architecture, Web UI, LLM
layer, Memory Layer, and this session's Companion integration). `pyproject.toml`'s
untouched `"0.1.0"` is, ironically, the more honest artifact of the two: it never
claimed a stability level the project hadn't earned.

### What repository state corresponds to a first stable version?

Not the state at either existing tag — both predate the working Reader MVP. The
state that has real grounds to be called "first stable" is the state that will exist
once this Product Readiness sequence (P01 License ✅, P02 CI ✅, P03 Changelog &
Versioning) completes: a real license, automated test verification, a working,
tested (512+ passing tests), documented CLI, and — for the first time — an honest,
maintained account of what changed and when.

### Keep the current numbering, or start fresh?

**Keep `pyproject.toml`'s numbering line (the `0.x` series it has used from the
start), do not adopt `v1.0.0`'s line.** Reusing "1.0.0" for the actual first
disciplined release would collide, in spirit, with an already-public tag that
disagrees with its own commit message and predates a working product — confusing
history, not clean history. Continuing the `0.x` series that `pyproject.toml` has
used unbroken since inception, and that `v0.1.0` (the annotated, more deliberate of
the two tags) already matches, is the throughline that's actually been consistent.

**A closely related, separate finding worth flagging for the Changelog Strategy
below**: this session's own Companion-integration work was tracked as "Reader M01-M04."
The *original* Reader pipeline has its own, older, unrelated milestone numbering that
reached **M021** (Memory Layer, `586d74b`) before this session began. "M01"-"M04" in
this session's `READER_M0X.md` reports and this session's commits **numerically
overlap with, but are conceptually unrelated to**, the pre-existing M006-M021 track.
The CHANGELOG must not let these two "M01"-shaped labels collide silently — see
Section 2.

## 2. Changelog Strategy

**Recommendation: [Keep a Changelog](https://keepachangelog.com) format** (the
project's own suggested example, confirmed as the right fit on its own merits, not
just accepted by default):

- Reverse-chronological version sections (`## [0.2.0] - 2026-07-27`), each with
  `Added`/`Changed`/`Fixed`/`Removed` sub-groups — maps directly onto real,
  already-written material: the `READER_M0X.md`/`P0X` reports already describe
  exactly this kind of change, just not yet in one consolidated, user-facing place.
  Compiling into this format is transcription of real history, not new investigation.
  Pairs naturally with semver (Section 5) — a `Changed`/`Removed` entry under a
  version is itself a semver signal (breaking vs. additive).
- Requires no tooling, automation, or CI integration to maintain — consistent with
  this project's current all-manual documentation discipline (every `READER_*.md`
  report so far has been hand-written, not generated).
- Widely recognized by anyone evaluating an open-source Python project, unlike a
  bespoke format that would need its own explanation.
- **A short "Note on early tags" line is recommended inside `CHANGELOG.md` itself**,
  addressing the `v0.1.0`/`v1.0.0` discrepancy from Section 1 directly, once, in the
  document most likely to be read by someone confused by `git tag -l` — rather than
  leaving that confusion to be silently rediscovered later.

## 3. Milestone Mapping

Scoped to this session's own, currently-active milestone track (Companion integration +
Product Readiness) — the track the CHANGELOG's first real version will actually
describe. The pre-existing M006-M021 track (Reader MVP through Memory Layer) is real,
substantial prior work, but predates this Product Readiness sequence and predates any
git tag that could honestly be called "first stable" (Section 1) — it belongs in
CHANGELOG.md as pre-1.0 historical background context, not as versioned entries
against a version number that didn't exist yet when it shipped.

| Milestone | Real changes (checked against commits/reports) |
|---|---|
| M01 — Contract Compliance | Reader reads Companion's Statement/Meeting objects per `companion-reader-contract.md` v1.0; forward/backward compatible (`extra="ignore"`, safe optional-field defaults). `companion show`/`companion search --signal`. |
| M02 — Signal Explorer | Meeting Summary, Signal Browser, full Signal View, combinable `signal:`/`speaker:`/`meeting:` search, global `companion stats`. |
| M03 — Object Navigation | `companion object`/`mentioned-in`/`relationships`/`timeline`; introduces (and explicitly flags as beyond Contract v1.0) `CompanionObject` and `Meeting.meeting_date`; found and fixed a real reindex-duplication bug (`filter_to_current_meetings`). |
| M04 — Promotion Review UI | `companion review` — Statements grouped by `statement_kind` only, no signal-combination classification (binding Design Principle established here for all future work). |
| P01 — Licensing | Added `LICENSE` (Apache-2.0); `pyproject.toml` `license`/`classifiers` fields set (were blank). |
| P02 — Continuous Integration | Added `.github/workflows/tests.yml` — checkout, setup-python (3.9), install, pytest. No lint/coverage/matrix/cache/release. |
| P03 — Changelog & Versioning (this task) | This document (Stage 1); `CHANGELOG.md` + version decision, pending confirmation (Stage 2). |

**Not included above, but real and worth CHANGELOG background context**: Phase 1-5
(Adapter/Normalizer core), M006-M010 (Reader MVP: Indexer/Registry/Retrieval/Composer/
CLI), M011-M017 (extensibility: workspace, plugins), M018 (Web UI), M019 (optional LLM
presentation layer), M020 (**design document only** — `MILESTONE-020-DESIGN.md`, no
implementation code exists for it, checked directly — must not be listed as shipped
functionality), M021 Phase 1 (Memory Layer — real, shipped code, `core/memory.py` +
`MemoryStore`).

## 4. Release Strategy

- **Cut a GitHub Release when, and only when, a version-number-worthy change lands** —
  i.e., not on every commit or every `P0X`/`M0X` internal milestone, but when the
  accumulated changes since the last release are enough to describe as a real version
  bump (see semver guidance below). Given this project's actual pace (four Companion
  milestones plus two Product Readiness items in one continuous session), that could
  reasonably mean the *first* real release covers all of P01-P03 plus M01-M04 as one
  coherent "first disciplined release," rather than one release per milestone.
- **Bump the version number at release time, not at milestone-completion time.** A
  milestone completing (e.g., M04) is a development-process event; a version bump is a
  distribution/consumer-facing promise. Keeping them decoupled avoids exactly the drift
  seen in Section 1, where tags got created ad hoc, disconnected from what
  `pyproject.toml` actually declared.
- **Link milestone → release via the CHANGELOG, not via git tags naming individual
  milestones.** A `## [0.2.0]` section can enumerate "M01-M04, P01-P02" in prose; there
  is no need for a `v-M04` or similar tag — one tag per real release, referencing the
  relevant milestones in its CHANGELOG entry and GitHub Release notes.
- **Every future release should**: bump `pyproject.toml`'s version, add a
  corresponding `CHANGELOG.md` section, then tag — in that order, so the tag always
  agrees with what the package itself declares (the one thing the existing `v1.0.0` tag
  never did).

## 5. Recommendation

**The first public release should be versioned `0.2.0`, not `1.0.0`, and not a
continuation of the orphaned `v1.0.0` tag's line. The version number is not being
changed in this document — this is a recommendation for Stage 2 to confirm.**

**Why `0.2.0`:**
- Semver's own stated meaning for the `0.y.z` range is explicit: the public API should
  not yet be considered stable, anything may still change. That is an accurate,
  honest description of Reader's actual current state — the `companion` CLI surface has
  grown by an entire subcommand set within this session alone, and two fields
  (`meeting_date`, `CompanionObject`) are explicitly still "beyond contract," unresolved.
  Declaring `1.0.0` now would assert a stability commitment this project hasn't
  actually made, on top of already-completed work, not yet tested by a real
  external consumer.
- A **minor** bump (`0.1.0` → `0.2.0`), not a patch (`0.1.1`), because everything
  shipped since the original `0.1.0` — the entire Reader MVP pipeline, extensibility
  architecture, Web UI, LLM layer, Memory Layer, and this session's full Companion
  integration plus License and CI — is substantial, additive, backward-compatible new
  capability, exactly what semver's MINOR category is for. None of it removed or broke
  an existing public interface.
- Deliberately **not** `1.0.0`, and deliberately **not** picking up after the existing
  `v1.0.0` tag: doing either would retroactively legitimize a tag that (Section 1)
  already contradicts its own commit message and predates a working MVP — cleaner to
  let that tag stand as an acknowledged historical artifact (documented in
  `CHANGELOG.md`, not deleted — it's already public on `origin`, and deleting a
  published tag is a separate, destructive action out of scope for this task) than to
  build the real version line on top of it.

**What Stage 2 would then do, pending confirmation**: bump `pyproject.toml`'s
`version` to `"0.2.0"`, and write `CHANGELOG.md`'s first real entry as `## [0.2.0]`
covering M01-M04 and P01-P02, with the "Note on early tags" from Section 2 explaining
`v0.1.0`/`v1.0.0`'s status. Nothing else.
