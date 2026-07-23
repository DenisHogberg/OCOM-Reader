# ADR-006: Classification Lifecycle and Human Override

**Status:** Accepted
**Date:** 2026-07-23
**Applies to:** the intended semantics of `OCOMObject.classification: list[str]` and `metadata["attributes"]["classification"]`, and how a human correction is expected to interact with both
**Builds on:** [OCOM Enrichment Provenance v0.1](OCOM-Enrichment-Provenance-v0.1.md) (directly resolves its Open Questions 3 and 4), [ADR-005](ADR-005-identity-resolution-signal-model.md), [OCOM Classification Engine v0.1](OCOM-Classification-Engine-v0.1.md)
**Not touched by this ADR:** `core/object.py` (`OCOMObject.classification` stays `list[str]`), `identity/resolver.py`, `intelligence/classification.py`. All three are frozen for this document; §6 names what a future implementation would need without performing it.

## Context

[OCOM Enrichment Provenance v0.1](OCOM-Enrichment-Provenance-v0.1.md)
decided *that* conflicts get preserved (append-only, never overwritten)
and named a precedence order (`human > llm > rule-based`) for what gets
promoted into the flat `classification` list — but left open exactly
what that flat list is *for*, what `IdentityResolver` should be reading
from it, and what a human override concretely does to data that
already exists. This ADR answers those directly.

## 1. Classification Semantics

The three options apply differently to the two places classification
data actually lives — treating them as one question produces the wrong
answer for one of the two:

- **`metadata["attributes"]["classification"]` (structured record) is
  Option C — a set of candidates with provenance.** This is not a new
  decision; it is what
  [OCOM-Enrichment-Provenance-v0.1.md §1](OCOM-Enrichment-Provenance-v0.1.md#1-who-added-the-knowledge)
  already specified (`domain`/`category`/`type` + `method` +
  `processor` + `evidence` + `confidence` + `timestamp` per entry).
  Confirmed here, not re-decided.
- **`OCOMObject.classification` (flat list) cannot be Option C at
  all — it structurally has nowhere to put provenance.** It is a
  `list[str]`. Calling a bare string "a candidate with provenance" is
  a category error, not a design choice. Between the two remaining
  options, **it is Option A — the current, precedence-resolved
  projection** consumers treat as ground truth without seeing
  alternatives. Not Option B (all known values, undifferentiated):
  that was already rejected in the Enrichment Provenance document's
  own dilution concern, and restated here for the same reason.

**"Confirmed" should not be read as "validated by a human or
governance process."** Nothing in this system currently validates
anything — most flat-list entries today come from
`intelligence/classification.py`'s rule-based matches alone. "Current
resolved projection" is the precise description; "confirmed state" is
Option A's label, used because it is the closest available word, not
because a confirmation step exists.

## 2. Where History Lives

**Reaffirmed, not re-litigated:** history — including rejected and
conflicting values — lives in `metadata["attributes"]["classification"]`,
append-only, exactly as
[OCOM-Enrichment-Provenance-v0.1.md §4](OCOM-Enrichment-Provenance-v0.1.md#4-immutable-history)
already decided. A separate "enrichment history" store is rejected
again for the same reason: it would be new infrastructure duplicating
what an append-only list already provides for free. An
`Evidence`-only approach is rejected because `Evidence.excerpt` is free
text — reconstructing "what was proposed and by what method" from it
would mean re-parsing prose to recover structure the attribute record
already holds directly.

**One addition, motivated directly by this task's "rejected values"
question, which the prior document left implicit:** each entry in
`metadata["attributes"]["classification"]` gets a `status` field —
`"active"` or `"superseded"`. Without it, a reader has no way to tell
"this is a live, unresolved disagreement" from "this was superseded
and is now historical" — silence would force every consumer to
re-derive that distinction from timestamps and the precedence rule
every time, which is exactly the kind of duplicated logic this
project's Modeling Rule 8 discipline has repeatedly avoided elsewhere.
This is one key inside an already-flexible dict record — not a Core
change, not a new namespace.

```python
metadata["attributes"]["classification"] = [
    {
        "domain": "Marketing", "category": ..., "type": ...,
        "method": "rule-based", "processor": "classification-engine-v0.1",
        "status": "superseded",   # NEW
        "evidence": [...], "confidence": "Medium", "timestamp": "...",
    },
    {
        "domain": "Partnership Operations", "category": ..., "type": ...,
        "method": "human", "processor": "...",
        "status": "active",       # NEW
        "evidence": [...], "confidence": "Verified", "timestamp": "...",
    },
]
```

## 3. IdentityResolver Input

**Decision: Option B — only accepted/current classification — which
`IdentityResolver` already reads unchanged, because the filtering work
happens upstream, not in the resolver.**

By the time an enrichment is written, precedence selection has already
run and the flat `classification` list already reflects only the
current, active projection (§1). `IdentityResolver` reading
`obj.classification` today is therefore already reading Option B — no
code change is required to make that true, and none is proposed.

**Option A (all values) is rejected** for the dilution reason already
established. **Option C (classification + provenance weighting inside
the resolver) is rejected** for a sharper reason than "unnecessary
complexity": doing provenance weighting *inside* `IdentityResolver`
would duplicate the precedence logic that
[Enrichment Provenance §3](OCOM-Enrichment-Provenance-v0.1.md#3-conflict-handling)
already assigned to the enrichment/promotion boundary — the same value
would be weighed twice, by two different components, using
(potentially) two different rules over time. `IdentityResolver` staying
untouched is not a workaround to satisfy this task's constraint; it is
the correct outcome of putting provenance-weighting logic in exactly
one place.

## 4. Human Override

The scenario: rule proposes `Marketing`; a human enters `Partnership
Operations`. **Answer: both — replace and add, but at different
levels, not in contradiction with each other.**

- **In the structured record (`metadata["attributes"]["classification"]`):
  strictly additive.** The rule's entry is never deleted or edited —
  its `status` flips from `"active"` to `"superseded"` (§2). A new
  entry is appended for the human's value, `method: "human"`,
  `status: "active"`. This is what "append-only" (Enrichment
  Provenance §4) actually means in practice: nothing is destroyed, the
  rule's proposal remains fully visible and attributed forever.
- **In the flat `classification` list: effectively a replacement.**
  Per §1, that list is a *projection* of whichever structured entries
  currently have `status: "active"` — not an independently-maintained,
  purely-appended list of its own. Once the rule's entry is superseded,
  its tag(s) drop out of the projection; the human's tag(s) appear in
  their place. `"Marketing"` stops being something `IdentityResolver`
  or `Registry` can match against; `"Partnership Operations"` starts
  being so.

**This sharpens, not reverses, Enrichment Provenance §4.** Append-only
was and remains the rule for the *history*. What this ADR clarifies is
that the flat list was never itself an independent append-only store —
it is a derived view, recomputed from active status, and treating it
as "just append and never remove" (which is what
`intelligence/classification.py`'s current, unmodified
`apply_classification()` actually does today) is a simplification that
holds only in the *no-conflict* case it was originally built and
tested against. A real override needs the projection to update, not
just grow.

**"Confirms" is a third, distinct action this ADR does not fully
specify.** A human agreeing with an existing proposal, without
supplying a new value, is meaningfully different from overriding it —
it should plausibly raise that entry's standing (e.g. its `status` or
an equivalent marker) without introducing a competing value. Whether
this needs its own `method` value, a boolean flag, or something else
is left open (§7) rather than decided without a concrete case to design
against — the same discipline
[OCOM-Classification-Engine-v0.1.md](OCOM-Classification-Engine-v0.1.md)
already applied to its own open naming question about `type`.

## 5. Impact on Agent and Identity Resolution

- **Identity Resolution: no impact, and this document explains exactly
  why rather than merely asserting it.** `IdentityResolver` already
  reads the flat list as Option B (§3); this ADR does not change what
  arrives there, only clarifies why what arrives there was already
  correct.
- **`Registry.find_candidates()`: a real, positive behavioral
  consequence, once implemented.** `Registry` searches `classification`
  values too ([ADR-002](ADR-002-agent-vertical-slice-boundaries.md) /
  [ADR-004](ADR-004-metadata-namespace-migration.md)). Under the
  current, unmodified `apply_classification()`, a stale rule-based tag
  would keep matching search queries forever, even after a human
  correction, because nothing ever removed it. Once the flat list
  becomes a recomputed active-only projection (§4), a query for
  `"Marketing"` correctly stops matching this object after the human
  override — search results follow the correction instead of ignoring
  it. This is a consequence of this design, not something `Registry`'s
  own code needs to change to benefit from — but it is worth stating
  plainly that this behavior does not exist yet, since
  `intelligence/classification.py` has not been updated to build the
  projection this way (§6).
- **`AnswerComposer`: a new, unclaimed capability, not an implemented
  one.** The `method`/`status` fields make a natural future answer
  possible — *"classified as Marketing by rule-based inference;
  corrected to Partnership Operations by human review"* — consistent
  with [OCOM Agent v0.1 Design §7](OCOM-Agent-v0.1-Design.md#7-evidence-handling)'s
  "surface, don't adjudicate" stance applied to enrichment instead of
  raw Evidence. Not built here; `AnswerComposer` is untouched.

## 6. Consequences — What This Implies for Existing Code

Named, not performed, same discipline as
[Enrichment Provenance §6](OCOM-Enrichment-Provenance-v0.1.md#6-consequences--what-this-implies-for-existing-code):

1. `metadata["attributes"]["classification"]` records need a `status`
   field (§2), defaulting new entries to `"active"`.
2. When a new proposal's value differs from an existing `"active"`
   entry for the same field (a genuine override, not an additional,
   non-conflicting tag), the prior entry's `status` must flip to
   `"superseded"` rather than simply leaving both `"active"` — this is
   new logic `apply_classification()` does not have today.
3. The flat `classification` list needs to be rebuilt from
   currently-`"active"` structured entries rather than
   append-if-not-present — a real behavioral change from today's
   implementation, not just an additive one.
4. A `"human"`-method entry point into `intelligence/classification.py`
   (or a sibling component) does not exist yet — this ADR specifies
   its effects, not its interface.

## 7. Open Questions

1. **How is "confirm" (§4) actually modeled** — new `method` value,
   boolean flag, or something else? Deferred pending a concrete case.
2. **What happens to `status` when a *third* method later disagrees
   with an already-superseded entry** — does history ever need more
   than a two-state `active`/`superseded` marker? Not tested against a
   three-way real case yet.
3. **Does recomputing the flat list from `"active"` entries ever need
   to consider more than one active entry per field simultaneously**
   (Meta/Classification.md.docx's "multiple classifications" allowance,
   already flagged as unresolved in
   [Enrichment Provenance §3](OCOM-Enrichment-Provenance-v0.1.md#3-conflict-handling))?
   Still open, carried forward rather than settled here.

## Decisions Recap

- `classification` (flat) and `metadata["attributes"]["classification"]`
  (structured) have different semantics because they have different
  capabilities: the flat list is the current resolved projection
  (closest to Option A); the structured record is the full candidate
  history with provenance (Option C).
- History stays where Enrichment Provenance already put it —
  append-only, in the structured record — with one addition: an
  `active`/`superseded` `status` field, so rejected values are
  distinguishable from unresolved conflicts without re-deriving that
  from timestamps every time.
- `IdentityResolver` reads Option B, already, without any change,
  because provenance weighting happens once, upstream, not in the
  resolver.
- Human override is additive in history, replacing in effect: the
  prior entry is marked superseded, never deleted; the flat list —
  understood as a projection, not an independent append-only store —
  reflects only the current active entry.

## Rejected Alternatives

- **Option B for the flat list's semantics** (all known values,
  undifferentiated) — rejected for signal dilution, consistent with
  every prior document touching this question.
- **Option C for `IdentityResolver`'s input** (provenance weighting
  inside the resolver) — rejected as duplicated logic, not merely
  unnecessary complexity.
- **A separate enrichment history store** — rejected as infrastructure
  duplicating what an append-only structured record already provides.
- **Treating the flat list as strictly append-only, with no
  recomputation** — rejected once a human override is in scope: it was
  only ever correct in the no-conflict case, and this ADR exists
  because that case has now been left.
