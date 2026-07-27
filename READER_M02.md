# Reader M02 — Signal Explorer

**Date:** 2026-07-27 · **Repository:** OCOM-Reader only — Vector was not touched
**Builds on:** `READER_M01.md` (Contract Compliance) — same `vector_integration/` package,
no changes to `models.py`'s field set, no change to Contract Version (still 1.0).

## Goal

Make signals a full part of Reader's interface — summary, browsing, richer single-Statement
view, combinable search, global statistics — without breaking Contract v1.0 compatibility.

## What changed

All additive, in `~/Downloads/OCOM-Reader` only:

- **`vector_integration/models.py`** — added `SIGNAL_DISPLAY_ORDER` (task, metric, risk,
  decision, question), a fixed rendering order distinct from `KNOWN_SIGNALS` (unordered,
  membership-only) and from `sorted(KNOWN_SIGNALS)` (alphabetical, used for CLI
  `choices=`). No field added or removed from either model.
- **`vector_integration/signals.py`** — added `signal_counts()`, `multi_signal_count()`,
  `zero_signal_count()`, `render_meeting_summary()` (Task 1), `render_signal_browser()`
  (Task 2). **Changed** `render_statement()`'s output format (Task 3) — see "Breaking
  change, scoped" below.
- **`vector_integration/query.py`** (new) — `parse_query()`/`apply_filters()`/`search()`:
  combinable `signal:`/`speaker:`/`meeting:` filters, ANDed. `signal:` still resolves
  through `filter_by_signal()` — one independent signal per query, never a combination
  (Task 5, unchanged discipline from M01).
- **`vector_integration/stats.py`** (new) — `compute_stats()`/`render_stats()` (Task 5 in
  the milestone's own numbering — "Statistics").
- **`cli.py`** — `vector search` extended with an optional `query` positional (M01's
  `--signal` flag kept working, mutually exclusive with `query`); three new subcommands:
  `vector signals <root>`, `vector summary <root>`, `vector stats <root>`.
- **`docs/vector-integration.md`** (new) — Task 6: supported contract version,
  compatibility, explicit limitations (including the honest one: `speaker:` search matches
  nothing useful yet, because Vector's real data never has a resolved speaker name — see
  below), CLI examples for every command.
- **`tests/test_vector_integration.py`** — 12 new tests (26 total in the file), covering
  every M02 function both in isolation and against Vector's real M07 data.

## Breaking change, scoped and deliberate

`render_statement()`'s output changed from M01's bare `Kind:`/`Detected Signals:` block to
the full Signal View (separators, `Speaker:`, `Kind:`, `Detected Signals` checklist, full
`Text`) — exactly what M02's Task 3 asked for. This is a **Reader-internal display
change**, not a Contract change: `vector-reader-contract.md` governs Statement's *data*
fields, never how Reader chooses to print them. M01's two tests that asserted the old
exact string were updated to assert the new format (`test_render_statement_full_signal_view`,
`test_render_statement_with_no_signals`) — nothing about the underlying `VectorStatement`
model or the contract's guarantees changed.

## An honest limitation, surfaced by actually running Task 4 against real data

`speaker:Denis` (a name) matches **zero** Statements in Vector's real corpus — verified
directly, not assumed. Every real Statement's `speaker` field is still a raw diarization
label (`"Speaker 1"`, `"Speaker 2"`) because Vector's own `speaker_resolved` is `False`
throughout its current data (documented in Vector's own `docs/ai-collaboration.md` roadmap
as not yet built). The filter itself works correctly — it would match `speaker:"Speaker 1"`
today — but the milestone's own example (`speaker:Denis`) can't succeed until Vector
resolves speaker identity on its side. Documented plainly in `docs/vector-integration.md`
rather than quietly working around it (e.g. by fuzzy-matching against some other field),
since that would misrepresent what's actually true about the data.

## Tests performed

**Isolated (12 new, synthetic fixtures)**: `signal_counts` reasons per-signal
independently; multi-/zero-signal counting; `render_meeting_summary`'s exact structure;
`render_signal_browser` shows all five groups even when empty, and a multi-signal
Statement correctly appears under *every* group it independently belongs to (not a
duplication bug); `parse_query`/`apply_filters`/`search` combine signal+speaker and
signal+meeting filters correctly, narrowing to the intersection; unknown filter keys and
repeated keys both raise; `compute_stats`/`render_stats` structure.

**Real data (4 new, against `~/Downloads/Vector` directly)**:
- `render_meeting_summary` numbers for `MTG-20260727-XMFL` cross-checked against
  `M06_RESULTS.md`'s own independently-reported Zero-signal (42, 43%) and Multi-signal
  (23, 23%) counts — agree exactly.
- `compute_stats` over the full real `ai/staging/` tree (10 Meetings, 900+ Statements
  across every re-ingestion from M03–M07) runs without error, every signal count
  non-negative.
- Combined `signal:risk meeting:XMFL` query against real data returns a strict, non-empty
  subset of the signal-only result, and every match genuinely satisfies both conditions.

**Regression**: `pytest tests/` — **482 passed** (470 from M01 + 12 new), zero failures.

**Manual CLI smoke tests**, real data — all shown working correctly in this session,
including: `vector summary` on a real Meeting; `vector stats` on the full staging tree
(Meetings 10, Statements 904, Tasks 68, Metrics 59, Risks 29, Decisions 13, Questions 120);
combined `signal:risk meeting:XMFL` query (12 results, all genuinely in that Meeting); the
`speaker:Denis` limitation above (0 results, correctly, not an error); M01's `--signal`
flag still working; `query` and `--signal` given together correctly rejected with a clear
error instead of silently picking one.

## Confirmation against completion criteria

| Criterion | Status |
|---|---|
| Reader shows signals | ✅ `vector show` (Signal View), `vector summary` (Meeting Summary), `vector signals` (Browser) |
| Reader can search by them | ✅ `vector search` — single-signal (M01-compatible) and combinable `signal:`/`speaker:`/`meeting:` queries |
| Reader can build summary statistics | ✅ `vector stats` |
| Contract v1.0 compatibility preserved | ✅ no field added/removed on `VectorStatement`/`VectorMeeting`; `extra="ignore"` untouched; full M01 test suite (backward/forward-compat, real mixed old/new data) still passes unmodified in behavior, only two display-format assertions updated to match the intentional Task 3 change |

## What Reader M02 deliberately does not do

Per the same roadmap M01 respected — explicitly separate, later milestones:
- No Object Navigation (M03) — no traversal UI between a Statement, its Meeting, and
  resolved Partner/Employee entities.
- No Timeline View (M04) or Promotion Review UI (M05).
- No integration into Reader's own `ask`/`search`/`explain`/`Reader` facade — `vector`
  remains a fully independent CLI subcommand, exactly as M01 left it.
- No resolution of the `speaker:` search limitation above — that requires a change on
  Vector's side (speaker identity resolution), not Reader's.
