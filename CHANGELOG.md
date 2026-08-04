# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Project History

This project's development has gone through three distinct epochs, using two
different, numerically-overlapping milestone-numbering schemes. Documented here
explicitly so "M01" is never ambiguous to a future reader — see
`READER_CHANGELOG_DESIGN.md` for the full analysis this is based on.

```
Legacy Development (M006–M021)
   The original Reader pipeline: Adapter/Normalizer core (Phases 1-5), the
   Reader MVP — Indexer/Registry/Retrieval/Composer/CLI (M006-M010),
   extensibility architecture (M011-M017), a Web UI (M018), an optional LLM
   presentation layer (M019), OCOM Expert Phase 1 design (M020 — design
   document only, no implementation), and a Memory Layer (M021 Phase 1).
   Predates this CHANGELOG and predates any git tag reflecting a working
   product — see "Note on early tags" below.
        │
        ▼
Reader Product — Companion Integration (M01–M04)
   A separate, restarted milestone count for Reader's Companion-integration
   work specifically: Contract Compliance (M01), Signal Explorer (M02),
   Object Navigation (M03), Promotion Review UI (M04). Numerically overlaps
   with M006-M021 above but is conceptually unrelated — a fresh count for a
   fresh, self-contained body of work.
        │
        ▼
Product Readiness (P01–P03, ongoing)
   Licensing (P01), Continuous Integration (P02), Changelog & Versioning
   (P03) — preparing Reader for its first disciplined public release.
```

## Note on early tags

`v0.1.0` and `v1.0.0` exist in this repository's git history and are already public
(pushed to `origin`), but do not reflect disciplined releases of the `ocom-reader`
package: both were cut before "Legacy Development" above had produced a working
Reader MVP; `v1.0.0` is a lightweight tag pointing to a commit whose own message reads
"docs: freeze OCOM Runtime v0.2 reliability milestone" — contradicting the tag's own
name; and `pyproject.toml`'s declared version was never updated to match either one.
They are left in place as historical artifacts, not deleted or reused. **`0.2.0` is
this project's first version number backed by an actual changelog and a disciplined
versioning process, and does not continue either tag's line.**

## [0.2.0] - 2026-07-27

### Added

- Companion integration (Reader M01-M04): read-only consumption of a Companion repository's
  Statement/Meeting/object data per `companion-reader-contract.md` v1.0, forward/backward
  compatible by construction.
- 10 new `ocom-reader companion` subcommands: `show`, `search`, `signals`, `summary`,
  `stats` (M01-M02 — signal-based search, browsing, and Meeting summaries); `object`,
  `mentioned-in`, `relationships`, `timeline` (M03 — Object View, reverse-navigation
  Mentions, Cross-Meeting View, a text-only Relationship Browser, an Entity Timeline);
  `review` (M04 — a Promotion Review queue grouping Statements by `statement_kind`,
  never by a `detected_signals` combination).
- `src/ocom_reader/companion_integration/` package: `models.py`, `loader.py`, `signals.py`,
  `query.py`, `stats.py`, `navigation.py`, `promotion.py`.
- A binding Design Principle for all future Companion-integration work (established in
  M04): Reader must not infer new semantic objects, create Promotion Candidates/
  Scores/Labels, or otherwise duplicate Companion's own business logic — it may only
  group, sort, and visualize data Companion has already contracted.

### Changed

- `companion_integration.navigation.linked_meeting_ids()`'s signature changed from
  `(object_id, statements)` to `(statements)` — takes an already-filtered Statement
  list instead of recomputing the filter internally, removing a redundant
  `linked_statements()` call inside `render_object_view()`. Internal API only; no
  `companion` CLI command's behavior or output changed.
- `pyproject.toml` gained `license` and `classifiers` fields (previously blank in
  package metadata — see Infrastructure).

### Fixed

- A real reindex-duplication bug in Object Navigation (M03): a single real Meeting
  reprocessed multiple times by Companion's own idempotent-import pipeline (same
  `source_hash`, different `parser_version`) was counted once per reprocessing run
  instead of once, overcounting Linked Statements/Meetings/Cross-Meeting View/Timeline
  results (confirmed 6x on real data before the fix). Fixed by
  `filter_to_current_meetings()`, reusing Companion's own `supersedes`-chain resolution.
- `linked_meeting_ids()`'s membership check used a `list` (`not in seen`) instead of a
  `set`, making it O(n·m) rather than O(n) — inconsistent with the rest of the module.
  Fixed alongside the signature change above.

### Documentation

- `READER_STATUS.md` — a single entry point summarizing current capabilities,
  contract dependencies (fields read beyond Contract v1.0, both flagged), known data
  limitations, and the standing design rules governing every future milestone.
- `READER_M01.md` through `READER_M04.md`, and `READER_M04_DESIGN.md` — a design
  review written and confirmed *before* M04's implementation, establishing the
  design-review-then-code discipline for future milestones.
- `docs/companion-integration.md` — supported contract version, compatibility
  guarantees, and CLI examples, updated across M01-M04.
- `READER_ROADMAP_REVIEW.md` — an architectural assessment of whether a new milestone
  (M05) was actually needed after M04, concluding in favor of stabilization first.
- `READER_PRODUCT_READINESS.md` — a full release-readiness audit (structure,
  documentation, GitHub infrastructure, build reproducibility) that identified the
  gaps Product Readiness P01-P03 close.
- `READER_LICENSE_REVIEW.md`, `READER_CI_DESIGN.md`, `READER_CHANGELOG_DESIGN.md` —
  design-review documents for P01, P02, and this release respectively.

### Infrastructure

- `LICENSE` (Apache License, Version 2.0) — Reader had no license at all before this;
  chosen over MIT/BSD-3-Clause specifically because Reader is a self-described
  reference implementation of the OCOM specification (itself Apache-2.0) with an
  existing plugin architecture inviting third-party Adapters (P01).
- `.github/workflows/tests.yml` — a minimal GitHub Actions workflow: checkout,
  setup-python (3.9, matching `pyproject.toml`'s declared floor), install, `pytest`.
  Deliberately no lint, coverage, matrix, cache, or release/publish step yet (P02).
- Version bumped `0.1.0` → `0.2.0` — the project's first version number to be backed
  by an actual changelog and a disciplined versioning process (P03; see "Note on early
  tags" above for why this is not `1.0.0` or a continuation of the existing tags).
