# Reader Roadmap Review — Is M05 Needed?

**Status: analysis only. No code written, no milestone started.** Written at the
user's explicit request, before any M05 work, to answer one question honestly: is a
new milestone actually justified right now, or has this reached a legitimate stopping
point for a first version? Every claim below was checked against the real repository
state (both `~/Downloads/OCOM-Reader` and `~/Downloads/Companion`) while writing this, not
recalled from the milestone reports.

---

## 1. Current State

**What Reader can do after M04** — 10 `companion` subcommands (`show`, `search`, `signals`,
`summary`, `stats`, `object`, `mentioned-in`, `relationships`, `timeline`, `review`),
512 passing tests, all exercised against Companion's real repository in addition to
synthetic fixtures:

- Read Statement/Meeting data per Contract v1.0, forward/backward compatible.
- Search and browse by signal (`metric`/`question`/`risk`/`task`/`decision`),
  independently or combined with speaker/meeting filters.
- Navigate objects: view an object's linked Statements/Meetings/aliases/relationships,
  reverse-navigate from a Statement to what it mentions, see cross-meeting mentions,
  walk a relationship tree, see a chronological mention timeline.
- Group Statements by `statement_kind` for human promotion review.

**User tasks already covered**: "what was said about X, and how confident is Companion in
it," "show me everything Companion's pipeline flagged as a possible task/decision/risk,
grouped for review," "where else does this person/partner get mentioned."

**Real, checked-just-now limitations** — not hypothetical:

- **No CI, no LICENSE, no CHANGELOG.** `find .github -type f` → doesn't exist.
  `pyproject.toml`'s version has been `0.1.0` through all four milestones. Four
  completed, tested, real-data-verified milestones have produced zero release
  artifacts.
- **The Companion integration is invisible from every other Reader surface.**
  `grep -n companion src/ocom_reader/web/api.py` → no matches. Same for
  `interactive.py` (the REPL). `README.md` → zero mentions of Companion, Statement,
  or `READER_STATUS.md`. Someone opening this repository fresh via its own front
  door would not discover that 10 commands and 512 tests of Companion integration exist.
- **Every `companion` command takes a raw filesystem path, every time.** Reader already
  has a named, persistent multi-repository mechanism (`ocom-reader repo add/use`,
  M016) — `companion_integration` was never wired to it. `companion review ~/Downloads/Companion`
  works; there is no `companion review` that resolves an active repo by name the way
  `ask`/`search`/`explain` already can.
- **Real Companion production data is narrow.** `objects/` has real files in only 2 of 12
  types (`partners/`: 4, `employees/`: 2 — checked just now; `companies/`, `decisions/`,
  `documents/`, `evidence/`, `issues/`, `products/`, `projects/`, `risks/`, `tasks/` are
  all empty). Every real Statement/Meeting seen so far carries `tenant: companion-primary`
  — multi-tenancy is a schema field, never yet exercised with a second real value.
  Speaker identity is unresolved on Companion's side (`speaker_resolved: false`
  everywhere), so `speaker:` search has never matched a real name.
- **Promotion Candidate data structurally doesn't exist in Companion** (confirmed during
  M04's design review) — M04 already routes around this by using `statement_kind`
  directly; this isn't a gap M05 could close either, since it isn't Reader's data to
  create.

## 2. Gap Analysis

Real scenarios a user might reasonably want, and whether they're solvable today:

| Scenario | Solvable today? | Real gap, or premature? |
|---|---|---|
| "Browse my Companion repo without retyping the path every time" | No | **Real, small.** The fix (wire into `repo`/`WorkspaceManager`) is mostly plumbing — the mechanism already exists and is proven in production for `ask`/`search`/`explain`. |
| "Search Statement *text*, not just signal/speaker/meeting metadata" | No | **Real, contained.** `query.py` filters by structured fields only; nothing greps `Statement.text`. Needs no new Companion field, no new contract dependency — the same "presentation over already-contracted data" discipline M04 followed. |
| "See this in the Web UI, not just the CLI" | No | **Real, but larger.** `web/api.py` has zero Companion wiring. Meaningful effort, and its value is capped by how few people are actually using this against real data yet (one tenant, one real company). |
| "Export a Promotion Review or Object View to share with someone non-technical" | No | **Real, low urgency.** Cheap to add later; nothing about the current design blocks it. |
| "See a richer 'this looks like a Task with a KPI' label, not just `statement_kind`" | No | **Not a Reader gap.** Blocked entirely on Companion publishing real Promotion Candidate data — M04's design review already established Reader must not invent this itself. No Reader milestone closes this. |
| "Navigate real relationships/aliases between objects" | Only against synthetic fixtures | **Not a Reader gap.** Blocked on Companion's real objects actually having `relationships`/`alias:` tags populated — 0 of 6 real objects do. More Reader-side relationship-browsing code wouldn't produce anything new to look at. |
| "Use this across two different companies' Companion repos" | Technically (pass a different path) but never actually exercised | **Validation gap, not a build gap.** The multi-tenant field exists; nothing has ever tested it with a second real tenant. |

**Which of these actually justify a new milestone**: the text-search and
workspace-wiring items are genuine, contained, buildable-today gaps. The rest either
require Companion-side changes Reader can't make happen (relationship data, speaker
identity, Promotion Candidates) or are legitimately deferrable (export, Web UI) given
how little real usage currently exists to justify the added surface area.

## 3. Need for M05

**Not right now — not as a new analytical feature.** Three converging reasons, each
grounded above rather than asserted:

1. **The stuff already built isn't finished being integrated.** No CI, no license, no
   changelog, and the entire Companion integration is undiscoverable from Reader's own
   README, Web UI, REPL, and workspace mechanism. Adding a fifth milestone of new
   capability on top of four milestones' worth of already-built-but-not-yet-surfaced
   capability compounds the same gap rather than closing it.
2. **Real Companion data hasn't grown enough to justify deeper analytical features.** M03's
   Relationship Browser and M04's design were both already built ahead of real data
   (0 populated relationships, 0 aliases, single tenant, 2 of 12 object types
   populated) — that was a reasonable bet twice, grounded and explicitly flagged both
   times, but making it a third time in a row without new real data arriving in
   between would stop being "building ahead of data" and start being "building into a
   vacuum."
3. **The two gaps that ARE real and buildable today (text search, workspace wiring) are
   small, not milestone-scale.** Neither needs a new Companion contract field, new
   Statement field, or new object data. Bundling them into a heavyweight "M05" process
   (a full design-review doc, the works) would be process overhead disproportionate to
   the actual work.

**What's the more correct next step**: a **stabilization pass** — closing the
release-hygiene and discoverability gaps found above — is higher-value right now than
new feature work, precisely because those gaps are real, checked, and currently make
four completed milestones' worth of work harder to find and harder to trust as
"finished" than the work itself actually is.

## 4. Possible Directions, evaluated against what actually follows from current state

- **New UI (Web/TUI).** Real gap, but premature — Reader's existing Web UI (M018)
  already exists and has zero Companion wiring; extending it is meaningful work whose
  payoff is capped by how little real multi-user usage exists yet. Defer.
- **Full-text search over Statement.text.** Real, contained gap — no Companion-side
  dependency, fits the existing `query.py` pattern, doesn't need new contract fields.
  The one candidate here that's actually milestone-shaped if feature work is chosen at
  all.
- **Filtering.** Already substantially covered (M02's combinable `signal:`/`speaker:`/
  `meeting:` query). Marginal value in extending further right now.
- **Export.** Real, low-urgency gap. Cheap; better treated as a small addition later
  than a dedicated milestone now.
- **Multi-repository support.** The infrastructure (`WorkspaceManager`, `repo`
  command) already exists in this codebase for Pipeline A and was simply never wired
  to `companion_integration`. This is the highest-leverage small change available — it
  reuses proven infrastructure, fixes a real daily friction point (always retyping a
  path), and requires zero new Companion data or contract changes. Not really "M05"-sized;
  more an integration-debt fix.
- **Plugin system / API.** Both exist (M017, M018) but are unrelated to Companion
  integration today. Speculative without a concrete third-party consumer in view — no
  evidence anyone needs this yet.
- **What actually follows from the current state, not from this list**: fixing the
  README/CI/LICENSE/CHANGELOG gap, and wiring `companion` into the existing workspace
  mechanism. Both are things the current, real state of the repository is already
  pointing at — not speculative additions.

## 5. Recommendation

**Stabilize M04 as the first complete version. Do not start a new analytical milestone
(M05) right now.**

Concretely, in priority order:
1. **Release hygiene**: `CHANGELOG.md` (summarizing M01-M04), a `LICENSE` file, a
   version decision (bump `pyproject.toml` to reflect four real, tested milestones — a
   decision only the user should make, not something to do unasked), and a minimal CI
   workflow (`pytest` on push) — the repository has none of these despite being tested
   more thoroughly than most 0.1.0 projects ever are.
2. **Discoverability**: a short Companion-integration section in `README.md` linking to
   `READER_STATUS.md` — currently a zero-cost fix for a total gap.
3. **Small integration-debt fix**: wire `companion` subcommand's `root` argument to
   resolve through the existing `WorkspaceManager`/`repo` mechanism as a fallback,
   the same way `ask`/`search`/`explain` already do — the single highest-leverage
   change identified above, and small enough not to need a full design-review
   milestone.

Only after that — and only if real usage or real Companion data growth actually surfaces
a need — would a genuine M05 (most likely full-text search, since it's the one
identified gap that doesn't depend on Companion producing more data) be justified. Until
then, more analytical features would be built ahead of both the data that would
validate them and the release/discoverability groundwork that would let anyone else
actually find and use what already exists.

---

## Roadmap critique

The proposed three-path roadmap (Product Stabilization / New Features / Productization)
is a reasonable shape, but as drawn it treats the three paths as parallel,
equally-available options. They aren't, given what's actually true about this
repository right now:

- **Path B (New Features, M05/M06/...)** is the path the evidence above argues against
  taking first — not because it has no future value, but because the two real
  prerequisites for it to pay off (release/discoverability hygiene, and richer real
  Companion data) haven't happened yet. Sequencing B before A risks repeating the exact
  pattern already seen twice (M03, M04) of building analytical capability ahead of the
  real data that would exercise it — reasonable once or twice as a bet, not as a
  standing default.
- **Path C (Productization — PyPI, TUI/Web UI, API, Plugins)** already has real
  infrastructure sitting unused for this specific integration: packaging is already
  possible (`pyproject.toml` has `[project.scripts]` and a `hatchling` build backend
  today), and the Web UI/plugin system already exist for Pipeline A. Path C isn't a
  future path so much as "finish wiring Companion into infrastructure that already exists"
  — which overlaps substantially with Path A's discoverability item, not a separate
  later phase.
- **Path A (Product Stabilization)** is therefore not just "one of three options" — it's
  the one path with zero prerequisites, addresses gaps already confirmed real (no CI,
  no license, no changelog, zero discoverability), and is what makes Paths B and C
  actually payable off later (a released, discoverable, CI-checked v1 is a better
  foundation for either more features or a PyPI package than an unreleased one).

**Revised framing**: not three parallel paths to choose between, but a sequence —
**A now, then B or C once A's prerequisites are met and either real Companion data grows
or a concrete Path-C consumer appears.** The original diagram's implicit suggestion
that "Foundation is done, now pick a direction" undersells how much of Path A is not
optional polish but a precondition the other two paths are silently assuming already
happened.
