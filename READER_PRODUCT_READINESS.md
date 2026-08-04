# Reader Product Readiness Audit

**Status: analysis only. No code, no docs, no config changed.** Written before any
Phase 2 work, to answer one question: is Reader ready to be a public, reproducible
open-source product, and if not, what closes the gap, in what order? Every claim below
was checked against the actual repository (`git log`, `git tag`, `pip show`, a live
`pytest` run) while writing this, not recalled from prior reports.

---

## 1. Current State

- **Milestones implemented**: the Adapter/Normalizer core (Phases 1-5), the Reader MVP
  pipeline (M006-M010), extensibility architecture (M011-M017), a Web UI (M018), an
  optional LLM presentation layer (M019), early OCOM Expert design work (M020), a Memory
  Layer (M021 Phase 1), and the Companion integration (Reader M01-M04: Contract Compliance,
  Signal Explorer, Object Navigation, Promotion Review).
- **CLI commands**: `ask`, `search`, `related`, `explain`, `repo` (4 sub-commands),
  `plugin` (5 sub-commands), `web`, `completion`, and `companion` (10 sub-commands) — 24
  total entry points under one `ocom-reader` executable.
- **Test coverage**: **512 tests, all passing** (`pytest tests/ -q`, just run), spanning
  36 test files. No coverage percentage is measured or enforced (no `pytest-cov`
  configured) — test *count* is known and verified; test *coverage* is not.
- **Documentation**: one `README.md` (258 lines) plus 46 files under `docs/architecture/`
  and 1 under `docs/research/`, plus 7 root-level `READER_*.md` reports from this
  project's own milestone-by-milestone discipline. Documentation volume is not the
  problem — organization and audience are (see Section 3).
- **Version status**: `pyproject.toml` declares `version = "0.1.0"` — **and has
  declared exactly that since the very first commit that introduced the file**
  (`git log --all -p -- pyproject.toml`, checked). Two git tags exist, `v0.1.0` and
  `v1.0.0`, both created the same day (2026-07-23, 2.5 hours apart) — but
  `pyproject.toml` at the `v1.0.0` commit itself still reads `"0.1.0"`. **The `v1.0.0`
  tag and the package's own declared version have never agreed, and 12 substantial
  feature commits (M011-M017 through this project's own M01-M04) have landed since that
  tag with no new tag and no version bump.** This is the single most concrete,
  unambiguous finding in this audit — not an absence, but an active inconsistency
  between two things that both claim to state "the version."

## 2. Release Readiness Audit

| Item | Status | Evidence |
|---|---|---|
| **README** | Needs Improvement | Exists, substantial (258 lines), has real install/run/test instructions — but organized as an internal engineering narrative (Phase 1-5, per-milestone implementation notes) rather than a product-facing entry point; contains a broken/out-of-repo relative link (`../Meta/Object.md.docx` resolves outside this repository entirely); zero mentions of the Companion integration, `companion` CLI, or `READER_STATUS.md` anywhere. |
| **LICENSE** | **Missing** | `find . -maxdepth 1 -iname "LICENSE*"` → no results. `pip show ocom-reader` confirms: `License:` (blank). No file in this repository currently grants anyone the legal right to use, modify, or redistribute it. |
| **CHANGELOG** | **Missing** | No `CHANGELOG.md` anywhere. The only change history is git log + scattered `READER_*.md`/`MILESTONE-*.md` reports — real records, but not a single chronological, user-facing account of what changed release-to-release. |
| **CONTRIBUTING** | **Missing** | No `CONTRIBUTING.md`. No documented contribution process, coding standards pointer, or PR expectations for an external contributor. |
| **GitHub Actions** | **Missing** | `.github/` does not exist in this repository at all — confirmed by `find`, not inferred. 512 passing local tests currently have zero automated verification on push or PR. |
| **Issue Templates** | **Missing** | Same root cause — no `.github/` directory means no `ISSUE_TEMPLATE/` either. |
| **Pull Request Template** | **Missing** | Same root cause. |
| **Release process** | **Needs Improvement** | Two tags exist (`v0.1.0`, `v1.0.0`), so *some* tagging habit exists — but it stopped 12 substantial commits ago, was never connected to `pyproject.toml`'s version field even when active, and there is no documented process (script, workflow, or written steps) for cutting the next one. |
| **Versioning** | **Needs Improvement** | `pyproject.toml` uses semver-shaped syntax correctly, but the value has been static since the file's first commit despite four completed, tested Companion-integration milestones alone (plus everything else since `v1.0.0`). Present as a mechanism, not maintained as a signal. |
| **Packaging** | **Needs Improvement** | `pyproject.toml` is real and functional — `hatchling` build backend, `[project.scripts]` entry point, `pip install -e .` works (verified: `pip show ocom-reader` succeeds). But `authors`, `license`, `classifiers`, and `urls` are all absent — a PyPI upload today would ship with a blank author, blank license field, and no homepage/repository link. |
| **Installation** | Needs Improvement | `pip install -e .` is documented and works — but appears three times in the README (`Reader MVP`, `Running`, `Testing` sections) with slightly different framing each time, none of them under a header a newcomer scanning for "installation" would reliably find first. |
| **Quick Start** | **Missing** | No section titled `Quick Start` or equivalent exists. The closest equivalent (`## Reader MVP`) is preceded by ~40 lines of architectural framing (`OCOMObject`, `Evidence`, ADR references) before the first runnable command appears. |

**Present, unambiguously, with no caveat**: `.gitignore` (covers the real cases: venv,
caches, build artifacts, `.ocom/`); the test suite itself (512 passing, real, exercised
against live Companion data where applicable); `pyproject.toml`'s basic mechanics
(build-system, dependencies, entry point) all functioning.

## 3. Repository Entry Experience

Read `README.md` top to bottom as a first-time visitor, not as someone who already
knows this project's history:

- **Is it clear what Reader does?** Partially. The opening paragraph leads with what
  Reader is *not* ("not a product, not a RAG, not a documentation chatbot") before
  saying what it is, and the very next paragraph introduces `RawDocument`, `ADR-007`,
  and "Operational Memory Platform" — internal architectural vocabulary, not a
  plain-language answer to "what is this and why would I use it."
- **Is it clear how Reader differs from Companion?** No — the distinction doesn't exist in
  this document at all. `README.md` contains zero occurrences of "Companion." Someone who
  has heard of Companion (a separate, real, sibling project) and lands on this repository
  has no way to learn from the README that Reader *reads* Companion's data, doesn't
  produce it, and is a completely separate codebase. This gap is total, not partial.
- **Is it clear how to get started?** Mostly, once you reach it — `pip install -e .`
  followed by a runnable `ocom-reader ask "..."` does appear, and it works (verified).
  But it's reached only after architectural framing that a newcomer evaluating "should I
  use this" would have to read through first, and it's the Reader MVP's start command
  only — there is no equivalent quick-start for the Companion integration's 10 commands
  anywhere in the README.
- **Is it clear what capabilities already exist?** No, for the Companion integration
  specifically. `READER_STATUS.md` is a genuinely good answer to this question — but
  the README never points to it, so a reader has to already know that file exists.

**Concrete improvements this points to** (not designed here, just identified):
a short "What this is / what it isn't" lead paragraph in plain language; an explicit
"Reader vs. Companion" callout early, linking to `docs/companion-integration.md` and
`READER_STATUS.md`; a `## Quick Start` section as close to the top as the license
badge, before any architectural history; fixing or removing the out-of-repo
`../Meta/...` links; moving the Phase 1-5 narrative and per-milestone implementation
notes to a `docs/history/`-style location, leaving the top-level README oriented at "use
this," not "here is how it was built."

## 4. Productization Roadmap

**Phase A — Foundation (no design decisions beyond a license choice; safe to do in
one pass)**
- Add `LICENSE`.
- Add `CHANGELOG.md`, backfilling M01 through M04 (and, if the user wants it, everything
  since the stale `v1.0.0` tag) from the existing `READER_*.md`/`MILESTONE-*.md` reports
  and git log — the raw material already exists, this is compilation, not investigation.
- Resolve the version inconsistency: decide what `pyproject.toml`'s version should
  actually say (a genuine open question — see Section 6), then make the tag and the
  file agree going forward.
- Add a minimal GitHub Actions workflow: run `pytest` on push/PR. Given 512 already-
  passing local tests, this is close to zero-risk — it codifies an already-true fact,
  it doesn't discover new failures to fix first.

**Phase B — Entry Experience**
- README redesign per Section 3's findings: lead with plain-language "what/why,"
  explicit Reader-vs-Companion distinction, a real `## Quick Start`, fixed/removed
  out-of-repo links, historical narrative moved out of the critical path.
- `CONTRIBUTING.md`.
- `.github/ISSUE_TEMPLATE/` + `PULL_REQUEST_TEMPLATE.md`.

**Phase C — Packaging & Distribution**
- Fill in `pyproject.toml`'s `authors`, `license`, `classifiers`, `urls`.
- A documented (or scripted) release process connecting a version bump, a
  `CHANGELOG.md` entry, and a git tag into one repeatable sequence.
- Actual distribution (PyPI publish, or a documented "install from GitHub" path) —
  only meaningful once Phase A/B are done, since publishing a package with a blank
  license and no changelog just moves today's gaps onto a public registry.

## 5. Priority

| Task | Impact | Effort | Risk | Priority |
|---|---|---|---|---|
| Add `LICENSE` | High — legal prerequisite for any external use at all | Trivial (one file, one decision: which license) | None — touches nothing else | **1** |
| Minimal CI (`pytest` on push) | High — protects the 512 already-passing tests from silent regression, cheap insurance | Low (one workflow file) | None — codifies a currently-true state, can't "discover" new failures that don't already exist | **2** |
| Resolve version inconsistency (`pyproject.toml` + tag) | High — currently the repo's own metadata contradicts itself | Low (edit one line) once the number is decided | Low — the only risk is picking the wrong number, which is a decision, not an execution risk | **3** |
| `CHANGELOG.md` | Medium-High — makes four (really more) real milestones legible to anyone who wasn't in this conversation | Medium (compiling from existing reports/log, not new investigation) | None | **4** |
| README redesign (Quick Start, Reader-vs-Companion, fix broken links) | High — this is the actual first thing every future user or contributor sees | Medium — a rewrite, not a patch, to do properly | Low — content-only, no functional risk, but easy to under-scope if rushed | **5** |
| `CONTRIBUTING.md` | Medium — mostly matters once external contributors actually show up | Low | None | **6** |
| Issue/PR templates | Low-Medium — nice for a public repo, not urgent pre-launch | Low | None | **7** |
| `pyproject.toml` metadata (authors/classifiers/urls) | Medium — only matters at the moment of actual PyPI publish | Low | None | **8** |
| Documented release process | Medium — valuable once versioning is fixed (item 3), redundant before | Medium | Low | **9** |
| Actual PyPI distribution | Depends entirely on items 1-8 being done first | Higher (registry setup, real publish) | Medium — a public, irreversible-in-spirit action | **10** |

Ranking logic: items with zero design decisions and zero risk of discovering new work
(1, 2, 3) come first regardless of impact ties, because they're the cheapest possible
progress. Items that depend on another item being decided first (9 depends on 3; 10
depends on nearly everything) are ordered after their prerequisite regardless of their
own standalone impact.

## 6. Final Recommendation

**The next commit should be: add a `LICENSE` file.**

**Why this one, specifically, and not CI, the version fix, or the README:**

- It is the only item in this entire audit that is a **hard, binary, legal blocker**
  rather than a quality-of-life or trust improvement. Every other Phase A/B/C item
  makes an already-usable-by-its-author project easier to trust, package, or contribute
  to. The absence of a LICENSE makes the project **not actually usable by anyone else at
  all**, in the literal legal sense — GitHub's own convention (and most jurisdictions'
  default copyright assumption) is that no license means all rights reserved, full stop.
  A 512-test, four-milestone, real-data-verified integration that nobody but its author
  has the legal right to run is not a smaller problem than a stale version number; it's
  a categorically different kind of problem.
- It requires **exactly one decision** (which license — MIT is the closest fit to how
  this project already describes itself, "a reference Adapter implementation" meant to
  be built on top of, which argues for permissive over copyleft, but that choice is the
  user's to confirm) and **zero investigation**. Fixing the version number correctly
  requires deciding what number is honest given everything that shipped since `v1.0.0`
  — a real judgment call this audit deliberately doesn't make unasked. CI requires no
  decision but has slightly more moving parts (workflow syntax, matrix, caching) than a
  single static file. LICENSE is the one item with strictly the least ambiguity and the
  least surface area, while still being the highest-impact single gap found.
- It is **the actual prerequisite the rest of the roadmap is implicitly assuming
  already happened.** Packaging metadata (Phase C) includes a `license` classifier that
  currently has nothing to point at. `CONTRIBUTING.md` (Phase B) can't meaningfully ask
  people to contribute code without stating what happens to it legally afterward.
  Sequencing anything else first means building the rest of Phase A/B/C on top of a
  project that, strictly, no one outside this session is yet allowed to use.

This is deliberately **not** a bundled "let's also add CHANGELOG and CI while we're at
it" recommendation — the instruction was one concrete commit, and the audit above
already shows those are real, close behind, and low-risk to do immediately after. But
LICENSE is the one item that is a precondition for the value of nearly everything else
in this roadmap, not merely parallel to it.
