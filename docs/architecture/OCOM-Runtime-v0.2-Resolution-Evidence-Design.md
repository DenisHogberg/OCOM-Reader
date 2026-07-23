# OCOM Runtime v0.2 — Resolution Decision Policy & Evidence Presentation Design

**Status:** Draft — design only, nothing in this document has been implemented.
**Date:** 2026-07-23
**Builds on:** [OCOM-Runtime-v0.2-Reliability-Design.md](OCOM-Runtime-v0.2-Reliability-Design.md) §5-§6 (extends and makes concrete, does not contradict), [MILESTONE-004](MILESTONE-004.md), [OCOM-Identity-Resolution-v0.1.md](OCOM-Identity-Resolution-v0.1.md), [OCOM-Object-Intelligence-v0.1.md](OCOM-Object-Intelligence-v0.1.md) §5.4
**Not touched by this document:** `core/`, `interfaces/`, `storage/`, `identity/`, `agent/`, `intelligence/`, `runtime/`. No code anywhere. This is a specification for changes future tasks would make to `runtime/pipeline.py` and a new, not-yet-created presentation module — neither is created here.

## 1. Purpose

`runtime/pipeline.py`'s `_resolve_against_storage()` (implemented,
committed at `20a2196`) currently does "first `MATCH` wins" — a rule
[OCOM-Runtime-v0.2-Reliability-Design.md §5](OCOM-Runtime-v0.2-Reliability-Design.md#5-resolution-decision-policy)
already named as a decided policy replacement for
(*"multiple simultaneous `MATCH` candidates are never auto-ranked and
picked... treated as ambiguity"*), but that replacement was never
implemented — `runtime/` is frozen for that document and every task
since. This document does the detailed work that policy needs before
it can be implemented: enumerating the specific candidate
combinations that can occur, and specifying exactly what happens in
each — plus, separately, the Evidence Presentation layer named but not
detailed in that same document's §6.

Nothing decided here reverses the prior document. Where this document
adds detail (the four cases, the audit-storage question, the
Presentation View's shape), it is called out as new; where it merely
restates a prior decision, it says so.

## 2. Current Runtime State

What `runtime/pipeline.py` actually does today, precisely, per
[MILESTONE-004](MILESTONE-004.md):

- `_resolve_against_storage()` compares a candidate against every
  stored object of the same `object_type`, pairwise, via
  `IdentityResolver.resolve()`.
- It folds the results: **first `MATCH` wins**, else **first
  `UNCERTAIN` wins**, else `NEW`. "First" means storage iteration
  order — not confidence, not any other principled ordering.
- A `MATCH` triggers an append-only evidence merge
  (`existing.evidence + candidate.evidence`) and `Storage.save()`.
  `UNCERTAIN` and `NEW` both persist the candidate under its own
  identity, never merged.
- The decision itself (`IdentityDecision` — `result`, `confidence`,
  `reasoning`, `matched_object_id`) is **not persisted anywhere**. It
  exists only as an in-memory return value
  (`IngestionResult.decision`) for the duration of one `ingest_document()`
  call. Once that call returns, the reasoning behind *why* a merge did
  or didn't happen is gone unless something outside this pipeline
  happened to log it.
- `Answer.sources` (`agent/answer.py`) presents `Evidence.reference`
  values as-is — including internal, non-human-facing strings like
  `evidence:fsdoc:35cc1254c5c7c489` when the `Evidence` was produced by
  `ClassificationEngine` rather than ingestion (MILESTONE-004
  Limitation 4).

Two concrete gaps this document addresses: the fold rule has never
been asked what to do when *more than one* candidate result is
non-`NEW` at once (this document's §4), and nothing decides what a
person should see instead of an internal reference string (§6).

## 3. Resolution Decision Policy

**Governing principle, restated because everything below derives from
it:** a false merge is more expensive than a duplicate. A duplicate is
a known, visible, reversible state — two objects that a later pass (or
a person) can still reconcile. A false merge silently blends two
provenance trails; by the time anyone notices, `Evidence` from two
unrelated things is indistinguishable inside one object's history.
Every rule in this section resolves ties toward the duplicate, never
toward the merge.

**Case A — one candidate, `MATCH` / `High`:**

- **Merge allowed:** yes. This is the only case where merge proceeds
  without further complication — a single, unambiguous, evidence-backed
  `MATCH` is exactly what `IdentityResolver` exists to produce.
- **Who decides:** `IdentityResolver.resolve()` produces the pairwise
  decision (unchanged, frozen). Applying it — actually calling
  `Storage.save()` with a merged object — remains orchestration's job,
  not the resolver's:
  [OCOM-Identity-Resolution-v0.1.md §1](OCOM-Identity-Resolution-v0.1.md#1-responsibility)
  already established `IdentityResolver` has no side effects and never
  decides what happens *after* a decision.
- **Where the decision is stored:** today, nowhere durable (§2). This
  document proposes closing that gap without touching `core/evidence.py`:
  record the merge decision as **another `Evidence` entry** on the
  resulting object, following the exact convention
  [OCOM-Object-Intelligence-v0.1.md §5.4](OCOM-Object-Intelligence-v0.1.md#54-evidence-model-integration)
  already established for enrichment — `source="runtime:identity-resolution"`,
  `reference` pointing at the matched object's prior identity,
  `excerpt` stating the decision in human-readable form (e.g.
  `"Matched and merged into concept:affiliate-manager — combined_score=0.94"`).
  No new field, no Core change: this is the same "reuse `Evidence` as
  the audit trail" pattern already proven, applied to identity
  decisions instead of classification decisions. Not implemented here
  — `identity/` and `runtime/` stay frozen for this document.
- **How evidence is preserved:** unchanged from today — append-only
  union (`existing.evidence + candidate.evidence`), plus, per the
  point above, one new entry recording the decision itself.

## 4. Multi-match Handling

**Case B — multiple candidates, all `MATCH`:**

```
Object A → MATCH
Object B → MATCH
```

**Decision: ambiguity, not a ranking problem.** Regardless of
confidence values attached to A and B, more than one existing object
scoring `MATCH` against one candidate is not evidence about which one
is "more correct" — it is evidence that `Storage` already contains two
objects close enough to be confused for each other, which is a
pre-existing data-quality condition this one ingestion did not create
and is not positioned to fix by guessing. **No merge.** The outcome is
`UNCERTAIN`, citing both A and B. This restates, not revises,
[OCOM-Runtime-v0.2-Reliability-Design.md §5](OCOM-Runtime-v0.2-Reliability-Design.md#5-resolution-decision-policy)'s
decision — this document adds the "why the pre-existing-ambiguity
framing matters" reasoning and the explicit case number.

**Case C — mixed result: one `MATCH`, one (or more) `UNCERTAIN`, for
different existing objects:**

```
Object A → MATCH
Object B → UNCERTAIN
```

**This is new territory — the prior document's fold rule
(`matches`/`uncertains` bucketing) already produces an answer for this
case mechanically, but never stated the reasoning, and this document
does.** **Decision: merge with A proceeds.** The reasoning: A's
`MATCH` is an independent, confident, evidence-backed decision about
the candidate's relationship to A specifically. B's `UNCERTAIN` says
something about the candidate's relationship to B — a *different*
question — not about whether A is the wrong choice. Treating B's
`UNCERTAIN` as a veto over A's `MATCH` would discard a working,
grounded signal because of unrelated noise elsewhere in storage; that
is not the same failure mode Case B protects against, where the
ambiguity is directly about *this* decision. **The `UNCERTAIN` is not
silently dropped, though:** it is recorded in the same `Evidence`-based
decision trail proposed in §3 (`excerpt`: e.g. `"Also compared
against role:partner-manager — UNCERTAIN, not merged"`), so a later
audit can see that B existed as a weaker, separate signal, without it
having blocked A's confident match.

**Case D — multiple candidates, none `MATCH`, one or more
`UNCERTAIN`:**

```
Object A → UNCERTAIN
Object B → UNCERTAIN
```

**Decision: `UNCERTAIN`, no merge — same outcome as a single
`UNCERTAIN`.** Cardinality doesn't change the decision: whether one or
several existing objects are ambiguously similar, none of them crossed
the bar for a confident claim, so none can be merged into. What
cardinality *does* change is the audit record — per §3's proposal, each
ambiguous candidate would get its own recorded mention, not just the
first one encountered (a direct fix for today's "first `UNCERTAIN`
wins" losing the others silently).

## 5. Merge Safety Rules

Distilled from §3-§4, stated as rules a future implementation must
satisfy:

1. **Merge requires exactly one `MATCH` among all candidates compared,
   full stop.** Zero `MATCH`es → no merge (`NEW` or `UNCERTAIN`,
   depending on whether any `UNCERTAIN` exists). More than one `MATCH`
   → no merge, downgrade to `UNCERTAIN` (Case B).
2. **A `MATCH`'s validity does not depend on the absence of unrelated
   `UNCERTAIN` results elsewhere** (Case C) — but every `UNCERTAIN`
   result, whether or not it changes the outcome, must be recorded,
   never silently discarded.
3. **No decision is ever applied without a recorded reason.** Every
   merge, and every refusal to merge, should be traceable to a
   specific `IdentityDecision.reasoning` — already true of the
   `IdentityResolver` output itself; §3 extends this to the
   fold-level decision, which today has no record at all.
4. **Nothing here changes `IdentityResolver`'s own thresholds, scoring
   formula, or `MATCH`/`UNCERTAIN`/`NEW` semantics** — this policy
   operates entirely on the *outputs* of pairwise comparisons already
   defined by [ADR-005](ADR-005-identity-resolution-signal-model.md),
   consistent with that document's own boundary.
5. **Ambiguity is a stable end state, not an error.** Per
   [OCOM-Identity-Resolution-v0.1.md §5](OCOM-Identity-Resolution-v0.1.md#5-failure-modes),
   `UNCERTAIN` — from Case B, C's flagged secondary signal, or Case D —
   requires no forced resolution. Two, or more, separately-stored
   objects that remain unreconciled is the correct, safe outcome until
   something with more authority (a human, or a future, better-evidenced
   pass) resolves it.

## 6. Evidence Presentation Architecture

```
Evidence
    |
    v
Presentation Mapper
    |
    v
Human Evidence View
```

**Where it lives:** a new module, not built by this document —
proposed as `runtime/presentation/`, sibling to `runtime/query/` and
`runtime/search/`, matching the precedent both already set (a small,
standalone, independently-testable unit before any wiring into
`agent/`). Not created here; `runtime/` stays frozen for this task.

**What it has the right to change:** nothing about stored `Evidence`.
It only ever *constructs a new, separate, read-only view* —
`HumanEvidenceView` — computed at presentation time and never written
back to `Storage`:

```python
class HumanEvidenceView(BaseModel):
    document: str            # human-facing location, resolved from the reference chain
    source_category: str     # a small fixed label derived from Evidence.source
    excerpt: str             # Evidence.excerpt, unmodified
    origin_evidence_id: str  # the real Evidence.identity this view traces back to
```

**What is forbidden to change:** the underlying `Evidence` instance —
`identity`, `source`, `reference`, `captured_at`, `excerpt` are read,
never written. The mapper also must not *fabricate* structure the data
doesn't have. The task's own example shows a target output including
`"Section: Responsibilities"` — restating the same honest limit named
in
[OCOM-Runtime-v0.2-Reliability-Design.md §6](OCOM-Runtime-v0.2-Reliability-Design.md#6-evidence-presentation-architecture):
nothing in `Evidence.reference` (a path) or `Evidence.excerpt` (a
quote) carries section-level structure today. A mapper that invented a
plausible-looking section label from nothing would be doing exactly
what this whole project has repeatedly refused to do — presenting an
unattributed claim as if it were grounded. This remains unbuilt until
`Evidence` (or something upstream of it) actually carries that
structure — not solved by presentation-layer invention.

**How the link to the original `Evidence` is preserved:** by
resolving the reference chain, not by discarding it.
[OCOM-Object-Intelligence-v0.1.md §5.4](OCOM-Object-Intelligence-v0.1.md#54-evidence-model-integration)
already established the signal needed: an `Evidence.source` starting
with `"object-intelligence:*"` (or, per §3 above, a future
`"runtime:identity-resolution"`) means its `reference` is *another*
`Evidence.identity`, not a location. The mapper:

1. If `source` does not start with a known internal prefix →
   `reference` is already human-facing; `document = reference`,
   `origin_evidence_id = identity` (it is its own origin).
2. If `source` does start with a known internal prefix → look up the
   `Evidence` on the same object whose `identity` equals this
   `reference`, and recurse (step 1 or 2 again) until a human-facing
   entry is reached. `origin_evidence_id` is always the identity of
   that final, human-facing entry — never the intermediate one — so
   the view is always exactly one hop, conceptually, from "what a
   person should look at," however many internal links it took to get
   there.

`source_category` is a small, fixed mapping (`"filesystem-documentation"`
→ `"Documentation"`; an `"object-intelligence:*"`/`"runtime:*"` prefix
→ `"Derived (<component>)"`) — mechanical, not inferred, consistent
with this project's standing refusal to use an LLM for anything that
doesn't need one.

## 7. Stable Decisions

- Merge requires exactly one `MATCH`; more than one, or any
  `UNCERTAIN` without a `MATCH`, never merges (§3-§5, Rule 1).
- A confident `MATCH` is not invalidated by an unrelated `UNCERTAIN`
  elsewhere in the same resolution pass (Case C) — but that
  `UNCERTAIN` must still be recorded, never dropped.
- The fold-level decision (as opposed to `IdentityResolver`'s own
  pairwise decision) should be recorded as an `Evidence` entry on the
  resulting object, reusing the exact convention already established
  for enrichment provenance — no new field, no Core or `identity/`
  change required to do this.
- Evidence Presentation is a read-only, external mapping. It may
  derive new display-only fields from existing `Evidence` data; it may
  never mutate `Evidence` or invent structure the data doesn't contain.
- The presentation link back to a human-facing source is always
  resolved via the existing `source`-prefix convention, chained if
  necessary, never a new pointer field.

## 8. Open Questions

1. **Does recording fold-decisions as `Evidence` entries risk cluttering
   an object's evidence list with audit noise** rather than content
   provenance, given both now share one list? Not tested — no
   implementation exists yet to observe this in practice.
2. **Should Case C's "flagged but not blocking" `UNCERTAIN` ever
   accumulate enough weight to retroactively block a future merge** —
   e.g., if the same ambiguous neighbor keeps showing up across many
   ingestions? Left open; nothing today aggregates decisions across
   calls.
3. **Where exactly does the reference-chain resolution in §6 stop** if
   a chain is unexpectedly long or (due to a future bug) cyclical? Not
   specified — no such case has ever occurred, so a bound is not
   invented pre-emptively.
4. **Does `IdentityDecision` (`identity/decision.py`) eventually need
   a structured list of "other candidates considered," instead of
   relying on `Evidence`-based audit entries for that?** Named again
   here (already an open question in the prior design document) —
   `identity/` remains frozen for this task, so this stays a future
   ADR's decision, not this document's.
5. **Should `HumanEvidenceView` ever be persisted (cached) rather than
   computed at every presentation**, once real usage shows it's
   expensive to recompute? Not addressed — no evidence yet that
   recomputation cost matters at this project's scale.

## 9. Non-Goals

- Embeddings
- Vector database
- New LLM agents — `source_category` mapping and reference-chain
  resolution are both mechanical, fixed-rule operations
- Any change to `OCOMObject`, `Evidence`, or any file under `core/`
  or `interfaces/`
- Any change to `IdentityResolver`'s scoring formula or thresholds —
  this document governs what happens to its *outputs*, not how they're
  computed
- A general confidence-ranking algorithm for choosing among multiple
  `MATCH` candidates — explicitly rejected (§4, Case B); ambiguity is
  surfaced, never resolved by picking a statistically "best" option
- Fabricating evidence structure (e.g. document sections) that
  `Evidence` does not currently carry (§6)
