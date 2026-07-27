# Reader README Review — Product Readiness P04

**Status: audit only, Stage 1. No README changes yet.** Per this task's own two-stage
structure (matching P03's discipline), Stage 2 — writing the actual new README — waits
for explicit confirmation of the structure proposed in Section 5, the same way P03's
version number waited for confirmation before being applied. Every finding below was
checked directly against the current, real `README.md` (258 lines, re-read in full
while writing this) and the current repository state, not recalled from memory.

---

## First Impression

Read top to bottom as someone who has never seen this repository, OCOM, or Vector:

- **Is it clear what Reader is, within 60 seconds?** No, not cleanly. The opening
  paragraph defines Reader by three negations ("not a product, not a RAG, not a
  documentation chatbot") before stating anything positive, and the very next
  paragraph introduces `RawDocument`, `ADR-007`, and "Operational Memory Platform" —
  internal architectural vocabulary a first-time reader has no context for yet. A
  concrete, plain-language "Reader is a CLI tool that does X for Y kind of user" never
  actually appears in the first three paragraphs.
- **Is it clear how Reader differs from Vector?** No — not partially, **totally**.
  Checked directly: `grep -i vector README.md` returns exactly one hit, and it's the
  phrase "no vector store" — describing the *absence* of vector-search technology in
  the original MVP pipeline. The word never once refers to the actual Vector
  repository. Someone who has heard of Vector and lands here has no way to learn from
  this document that Reader reads Vector's data, is a separate codebase, and doesn't
  modify anything Vector produces. This is the single largest gap found in this audit.
- **Is it clear what problem Reader solves?** Partially, but for an outdated scope.
  "Indexes this repository's own Markdown documentation and answers questions about
  it" accurately describes the original Reader MVP (M006-M010) — but says nothing
  about everything built since: reading and reviewing a *separate* Vector repository's
  operational data (10 `vector` subcommands), working across multiple repositories by
  name (`repo add`/`use`), a Web UI, or a plugin system. The stated problem is real but
  represents roughly the first third of what Reader can actually do today.
- **Is it clear who needs Reader?** No — no sentence in the document names an intended
  user or use case ("a developer who wants to...", "a team lead who needs to..."). It
  has to be inferred from reading the whole thing.

## Navigation

Checked whether each of the following can actually be found quickly:

| Looking for | Findable? | Notes |
|---|---|---|
| Installation | Present, but scattered | `pip install -e .` appears three times (`Reader MVP`, `Running`, `Testing`), each with slightly different framing, under none of which is titled "Installation." |
| Running / Quick Start | Present, delayed | The first runnable command is reached only after ~85 lines of architectural framing (the opening paragraphs, "Architectural principles," "Structure"). No section is titled "Quick Start." |
| Examples | Minimal, narrow | Four one-line `ask`/`search`/`related`/`explain` examples exist. Nothing demonstrates any of the other 20 real CLI subcommands (`repo`, `plugin`, `web`, `vector` ×10). |
| CLI reference | **Missing** | No comprehensive list of Reader's actual command surface exists anywhere in the README. |
| Architecture | Present, disproportionately so | ~180 of 258 lines (roughly 70% of the document) are the historical Phase 1-5 / `core`/`interfaces` architecture narrative — thorough, but so large it pushes everything else (installation, CLI, Vector integration) below the fold. |
| Documentation (pointer to `docs/`) | **Missing** | No summary or index of `docs/architecture/` (46 files), `docs/vector-integration.md`, or any of the seven root-level `READER_*.md` reports — including `READER_STATUS.md`, which was written specifically to serve as an entry point, but is never linked from the actual entry point. |

## Technical Accuracy

- **Broken links, confirmed**: five links point outside this repository entirely and
  do not resolve —
  [`../Meta/Object.md.docx`](../Meta/Object.md.docx),
  [`../Core/Principles.md.docx`](../Core/Principles.md.docx),
  [`../Core/Modeling-Rules.md.docx`](../Core/Modeling-Rules.md.docx),
  [`../Memory/Memory Record.md.docx`](../Memory/Memory%20Record.md.docx),
  [`../Memory/Evidence Overlay.md.docx`](../Memory/Evidence%20Overlay.md.docx) — verified
  with `ls ../Meta` from the repository root: `No such file or directory`. Every
  other link in the README (nine `docs/architecture/*.md` and `tests/*.py`/`src/*.py`
  references) was checked individually and resolves correctly — the breakage is
  isolated to this one block of five external, docx-targeting links, not widespread.
- **Outdated or incomplete commands**: not literally wrong (`ask`/`search`/`related`/
  `explain` still work exactly as documented), but silently incomplete — the README
  documents 4 of Reader's 24 real CLI entry points (`ask`, `search`, `related`,
  `explain`; missing `repo` [4 subcommands], `plugin` [5 subcommands], `web`,
  `completion`, and `vector` [10 subcommands]).
- **Version numbers**: no literal wrong number is printed anywhere in the README (it
  never states a version at all) — but that absence is itself now an inconsistency:
  the project has a real, disciplined version (`0.2.0`, per `pyproject.toml` and
  `CHANGELOG.md`, both confirmed current) and zero acknowledgment of it in the
  document most people will read first.
- **Missing sections relative to current project state**: no mention of `LICENSE`
  (added in P01), no mention of `CHANGELOG.md` or the version number (added in P03), no
  mention of `.github/workflows/tests.yml` (added in P02) — three real, shipped
  maturity signals this Product Readiness sequence produced, none visible from the
  README.
- **Overall inconsistency**: the document's own self-description — `pyproject.toml`'s
  `description` field still reads "Phase 1: architectural core" — reflects the
  project's state as of roughly its third or fourth commit, not its current one (21+
  commits, four Vector-integration milestones, three Product Readiness items later).

## Missing Content

Checked against the task's own example list, plus what the audit above surfaced:

| Section | Status |
|---|---|
| Features | Missing — no concise capability summary exists anywhere |
| Quick Start | Missing — closest equivalent buried under ~85 lines of architecture-first framing |
| Installation | Present, but duplicated three times with no canonical location |
| CLI Reference | Missing — 20 of 24 real subcommands are undocumented in the README |
| Examples | Present, but narrow — covers only the original 4-command MVP surface |
| Integration with Vector | **Missing entirely** — the largest and most consequential gap in this audit |
| Architecture Overview | Present, but overwhelming relative to its current proportional importance |
| Limitations | Present only in scattered, buried asides (e.g., a note that `Evidence` is "a minimal Phase 1 placeholder") — no consolidated section |
| Status | Missing — `READER_STATUS.md` exists and answers this exactly, but isn't linked |
| Roadmap | Missing — `READER_ROADMAP_REVIEW.md` exists and answers this, but isn't linked |
| License | Missing — `LICENSE` exists (Apache-2.0, since P01) but is never mentioned |
| *(not in the task's list, found during this audit)* Badges | Missing — no license/CI/version badge exists, despite all three now being real and checked-good (`pip show` confirms `0.2.0`/Apache-2.0; `.github/workflows/tests.yml` exists and was verified to pass on a clean checkout in P02) |

## Recommendation

**Proposed structure** (not written out in full — structure and rationale only, per
this task's own Stage 1 scope):

```
# OCOM Reader
[badges: license, CI status, version]

One-paragraph overview — including, explicitly, in this same paragraph,
not a separate section: "Reader reads Vector's data; it is a separate
project and does not modify it." This is the single highest-value
sentence this rewrite adds, given the First Impression findings above —
it belongs in the first 60 seconds, not several screens down in a
dedicated Vector section someone may never scroll to.

[table of contents]

## Features
## Installation
## Quick Start
## CLI
   (a curated, example-driven tour of the most-used commands across all
   four groups — ask/search/explain/related, repo, vector, web — each
   with one real example, plus a single explicit pointer: "run
   `ocom-reader --help` or see docs/vector-integration.md for the
   complete command reference." Not a full flag-by-flag manual — that's
   argparse's own --help output, and a README copy of it would just be a
   second copy that goes stale.)
## Working with Vector
   (what Vector is, in one sentence; what Reader can and cannot do with
   it — read-only, no promotion, no write-back; a link to
   docs/vector-integration.md for the full contract.)
## Architecture
   (a short overview + links out — NOT the full Phase 1-5 historical
   narrative currently in README.md. See "Where the historical content
   goes" below.)
## Current Status
   (a trimmed version of READER_STATUS.md's own content, or a direct
   link to it — including a short Limitations subsection, rather than a
   separate top-level heading, to avoid a longer table of contents than
   the content warrants.)
## Documentation
   (an index: docs/vector-integration.md, docs/architecture/, and the
   root-level READER_*.md reports, so a reader who wants more never has
   to guess a filename.)
## Roadmap
   (a short pointer to READER_ROADMAP_REVIEW.md's actual conclusion —
   not a restatement of it.)
## License
   (one line: Apache-2.0, link to LICENSE.)
```

**Why this shape, specifically:**

- It matches the structure already proposed for Stage 2, with three concrete
  refinements grounded in this audit rather than accepted by default:
  1. **Badges immediately under the title** — near-zero cost, and directly answers
     the "is this maintained/trustworthy" question a first-time visitor asks before
     reading a word, using exactly the maturity signals P01-P03 already produced.
  2. **The Vector distinction folded into the opening paragraph itself**, not
     deferred to the "Working with Vector" section — the First Impression findings
     above show this gap is total, not partial, and a reader skimming the top of the
     page should not be able to miss it.
  3. **The historical Phase 1-5 / M006-M021 narrative relocated out of README.md
     entirely** (proposed destination: a new `docs/HISTORY.md`, or folded into
     `docs/architecture/`'s own index) rather than compressed in place — at ~70% of
     the current document's length, compressing it in place would still leave it
     dominating the page; moving it preserves every word of real, valuable history
     (nothing here is proposed for deletion) while actually fixing the "first 60
     seconds" problem this whole task exists to solve.
- **CLI section is curated, not exhaustive**, by design: a full flag-by-flag
  reference in the README would duplicate `argparse`'s own `--help` output and would
  need updating every time a flag changes — a maintenance burden with no offsetting
  benefit over pointing to `--help` and `docs/vector-integration.md` directly.
- **Limitations folds into Current Status rather than becoming its own top-level
  section** — the content genuinely belongs together (what works today, and what
  doesn't, are the same conversation), and keeps the table of contents from growing
  past what a 5-minute read can absorb.
- **Every "missing" item from Section 4 above has an explicit home** in this
  structure — none are dropped, and none require inventing new content: `READER_STATUS.md`,
  `READER_ROADMAP_REVIEW.md`, `docs/vector-integration.md`, `LICENSE`, and
  `CHANGELOG.md` all already exist and are simply being linked from the one place a
  first-time visitor actually starts.

---

## Stage 2 — 5-Minute Test: an actual experiment, not just a link check

Per the added requirement: an actual run-through, not a review of the text. A fresh
copy of the repository (current working tree, `.venv`/`.git`/caches excluded) was
placed at a scratch path with a **brand-new virtualenv** — no reuse of this session's
own `.venv` — and the new README was followed exactly as written, command by command,
with no outside knowledge applied beyond what's on the page.

1. `git clone .../OCOM-Reader.git && cd OCOM-Reader` — simulated via a clean directory
   copy (identical effect for this purpose; the git mechanics of `clone` itself aren't
   in question).
2. `pip install -e .` — **worked cleanly**, zero errors, `pip show ocom-reader`
   afterward confirms `Version: 0.2.0`.
3. `ocom-reader ask "identity resolution"` — **worked**, returned a real, substantive
   answer. One honest observation, not a defect: the output is a long, dense wall of
   13 scored documents plus "Related Documents" — accurate and useful, but not a
   crisp, confidence-inspiring first command for a brand-new user. Not something
   fixed here (it's `AnswerComposer`'s existing, tested output format — changing it
   would be changing code, out of scope for a README task), but worth naming rather
   than silently glossing over.
4. `ocom-reader vector stats path/to/vector-repo` (run against the real
   `~/Downloads/Vector` repository, substituted for the placeholder) — **worked**,
   clean, short, immediately legible output (Meetings/Statements/Tasks/Metrics/Risks/
   Decisions/Questions counts).
5. `ocom-reader vector review path/to/vector-repo` — **worked**, produced exactly what
   the README promises: Statements grouped by kind, ready for a human to look through.

**No step required guessing, and no step required opening any file besides
`README.md` itself.** The one placeholder (`path/to/vector-repo`) is self-explanatory
in context and was resolved correctly on the first try using a real Vector repository.

**Link check**: every file reference in the new `README.md` — both markdown links and
plain-text/bold file-path mentions — was checked programmatically against the real
filesystem. All resolve. `docs/HISTORY.md`'s own relocated cross-references
(to `docs/architecture/`, `tests/`, `src/ocom_reader/normalizers/`) were checked the
same way and also all resolve.

**Regression**: full `pytest tests/` — 512 passed, unchanged — this task touched only
`README.md` and added `docs/HISTORY.md`, no source code.

**One disclosed, non-blocking caveat**: the `Tests` badge in the new README points at
`.github/workflows/tests.yml`'s GitHub Actions run status. Since these commits haven't
been pushed to `origin` yet, the badge won't reflect a real passing run until they are
— this is an accurate statement about *when* the badge becomes meaningful, not a defect
in what was written.

**Conclusion: the 5-minute test passes.** Clone → install → run → point at a real
Vector repository → get a genuinely useful first result, entirely from `README.md`
alone.
