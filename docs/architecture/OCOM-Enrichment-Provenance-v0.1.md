# OCOM Enrichment Provenance v0.1 — Design

**Status:** Draft — design only. No code changes proposed or made by this document.
**Date:** 2026-07-23
**Builds on:** [OCOM Classification Engine v0.1](OCOM-Classification-Engine-v0.1.md), [OCOM Object Intelligence Layer v0.1 §5.3-5.4](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment), [ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-004](ADR-004-metadata-namespace-migration.md)
**Not touched by this document:** `core/object.py`, `core/evidence.py` (Evidence model unchanged — no `confidence`, `method`, or `processor` field added to it), `identity/resolver.py`, `intelligence/classification.py` (the existing rule-based implementation is not modified here, though §6 names what it would need). No LLM, no hybrid resolution logic.

## Context

The Classification Engine v0.1 experiment
([OCOM-Classification-Engine-v0.1.md](OCOM-Classification-Engine-v0.1.md))
proved a working rule-based enrichment path and, in doing so, exposed
what it doesn't yet handle: `test_semantic_neighbour_produces_only_a_
partial_classification` showed rule-based coverage has a real ceiling,
which means a second enrichment method (LLM, or a human correcting a
wrong tag, or a value imported from an external system) is a question
of *when*, not *if*. The moment a second method exists, one object can
carry knowledge from more than one origin — and nothing in this
project has yet decided how that's told apart, or what happens when
two origins disagree.

This document is that decision, made before a second method exists —
the same sequencing this project has followed at every layer so far:
contract before implementation, not implementation followed by a
retrofit.

## 1. Who Added the Knowledge

Two dimensions, not one, both new keys within the *already-existing*
structured attribute shape
([OCOM-Object-Intelligence-v0.1.md §5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment)) —
no new top-level namespace, no Core change:

```python
metadata["attributes"]["classification"] = [
    {
        "domain": "Partner Management",
        "category": ...,
        "type": ...,
        "method": "rule-based",                       # NEW
        "processor": "classification-engine-v0.1",     # NEW
        "evidence": [...],
        "confidence": ...,
        "timestamp": ...,
    }
]
```

- **`method`** — a small, fixed set: `"rule-based"`, `"llm"`,
  `"human"`, `"external"`. This is the categorical dimension the §3
  conflict rule and any future trust policy reasons about — coarse by
  design, not meant to grow into a taxonomy.
- **`processor`** — a specific, nameable origin within that method:
  `"classification-engine-v0.1"` for rule-based today; a model/version
  identifier for `"llm"`; a reviewer or role identifier for `"human"`;
  a system name for `"external"`.

**Why this is not redundant with `Evidence.source`**, which already
carries a similar-looking string (`"object-intelligence:classification-
engine"`, per
[OCOM-Object-Intelligence-v0.1.md §5.4](OCOM-Object-Intelligence-v0.1.md#54-evidence-model-integration)):
`Evidence.source` answers *which architectural layer* produced a piece
of evidence (Object Intelligence, vs. a Normalizer, vs. eventually a
human review tool) — it is frozen and not reinterpreted here.
`method`/`processor` answer a narrower question one level down: *which
technique, and which specific instance of it*, produced this one
enrichment value. A future human-review tool and a future LLM-based
Classification Engine would likely share the same `Evidence.source`
namespace (`"object-intelligence:*"`) while having completely
different `method` values — that distinction only exists at this
level, not at `Evidence.source`'s.

**On identifying "which human":** left open, not decided. A literal
person's name is a governance/privacy question this document is not
equipped to answer (Meta/Ownership.md.docx frames accountability in
terms of roles more than individuals). `processor: "human"` cases may
need a role or team identifier rather than a name — named as an open
question (§8), not resolved here.

## 2. Confidence Model: Evidence Confidence vs. Enrichment Confidence

These are different claims about different things, and conflating them
would undo exactly the kind of separation ADR-003 already made for
`metadata` itself:

- **Enrichment confidence** — *"how sure is this specific derivation?"*
  This already exists: the `confidence` field already present in
  `metadata["attributes"][...]` records
  (`"Medium"` for a keyword match, per the existing
  `intelligence/classification.py` implementation). It describes the
  inference, not the underlying source.
- **Evidence confidence** — *"how reliable is the underlying source
  this was derived from?"* This is a real, separately defined concept
  in Memory/Confidence.md.docx ("Confidence is a measurable assessment
  of the likelihood that a Memory Record accurately represents
  reality," driven by "evidence quality... source reliability...
  human verification"). It is a property of the *source*, not the
  derived value.

**These are not the same axis, and collapsing them would hide a real
distinction:** a high-confidence classification derived from a
low-reliability source (an unverified external scrape) is a different
epistemic situation than the same classification derived from a
verified internal document, even if the rule-based inference itself
was equally mechanical in both cases.

**Honest gap, not solved here:** `Evidence` has no `confidence` field
today (by design — see `core/evidence.py`'s own docstring, and this
document is barred from changing it), so **Evidence confidence
currently has no storage location anywhere in this codebase.** This
document does not invent one. It names the gap so a future ADR can
close it deliberately — likely by extending Evidence Overlay /
Confidence Model work that was always out of scope for this project's
current phase (`core/evidence.py`: *"No confidence scoring... those
belong to the real Memory/Confidence Model... out of scope for the
Reader today"*), not by smuggling a `confidence` field into `Evidence`
through this document.

## 3. Conflict Handling

The scenario: rule says `domain = Marketing`; LLM says
`domain = Sales`; human says `domain = Partnerships`. Nothing today
decides a winner, and this document does not invent an algorithm that
does.

**Decision: no automatic resolution of "the truth." All three
proposals are preserved, in full, with their own `method`/`processor`/
`evidence`/`confidence`/`timestamp`.** This is not a new principle —
it is the same stance [OCOM Agent v0.1 Design §7](OCOM-Agent-v0.1-Design.md#7-evidence-handling)
already took for conflicting `Evidence` ("v0.1 does not pick a winner...
newer, conflicting evidence is still appended and still visible"), and
the same one [OCOM-Object-Intelligence-v0.1.md §10](OCOM-Object-Intelligence-v0.1.md#10-non-goals)
already committed the whole layer to ("surfaced via multiple
Evidence-backed entries... not adjudicated"). Silently picking a winner
among three independently-sourced proposals would be exactly the
"autonomous decision" that document's own principle already ruled out.

**A separate, narrower question does need an answer: what goes into
the flat, top-level `classification: list[str]` field that
`IdentityResolver` actually reads (ADR-003/ADR-005)?** That field
cannot hold "three disputed values, unresolved" the way the structured
record can — `IdentityResolver` treats whatever is there as
uncontested signal.

**Decision: a documented precedence order, used only to select what is
promoted to the flat list — never to delete or override the losing
proposals in the structured record.** `human > llm > rule-based`.
Reasoning: this ranks methods by how much independent judgment and
accountability stands behind them, not by any claim about which is
more likely to be factually correct — a human correction is treated as
the most authoritative signal for *acting on* even though a rule-based
tag might occasionally happen to be right where a human was careless.
`external` is deliberately left out of this ordering — a value
imported from another system carries its own, system-specific
trustworthiness this document has no basis to rank against the other
three.

**A named tension, not resolved:** Meta/Classification.md.docx states
an Object *"may belong to multiple Classifications simultaneously."*
Promoting only the precedence-winning tag to the flat list is a
narrower reading, chosen to keep `IdentityResolver`'s signal from being
diluted by disputed values (per
[ADR-005](ADR-005-identity-resolution-signal-model.md)'s own caution
about calibrating signals without real data). Whether that is the
right long-term reading, once real conflicting enrichment exists, is
left open (§8).

## 4. Immutable History

**Decision: append-only.** Not overwrite, not a separate versioning
mechanism.

- **Overwrite is rejected outright** — it would destroy exactly the
  provenance this document exists to preserve, defeating its own
  purpose in the same motion.
- **A dedicated "versioned enrichment" mechanism is rejected as
  premature infrastructure**, for the same reason
  [ADR-004](ADR-004-metadata-namespace-migration.md) rejected a
  `metadata_schema_version` field: it would be new machinery built for
  a pattern (repeated, conflicting re-classification) that has not
  happened yet even once in this codebase — only rule-based
  classification exists; there is no second method yet to conflict
  with it.
- **Append-only already gives the same outcome a version history
  would, using structure that already exists:** each new proposal is a
  new entry in `metadata["attributes"]["classification"]`, carrying
  its own `timestamp`. "What do we currently believe" is the most
  recent entries (or the precedence winner, §3); "how did that
  understanding evolve" is answerable by reading the list in order.
  No separate `version` counter is needed to get either answer.

**This decision matches, not merely permits, the current
implementation:** `intelligence/classification.py`'s
`apply_classification()` already appends to
`metadata["attributes"]["classification"]` and to the flat
`classification` list (`if tag not in classification: classification.
append(tag)`) rather than overwriting either. That code was written
before this ADR and already does the right thing — this document
explains *why* that was correct, and extends the same rule to
`method`/`processor`/multi-source conflicts it does not yet handle.

## 5. Non-Goals

- No LLM — the `"llm"` method value is named as part of the model; no
  LLM-based enrichment is implemented or specified here.
- No Hybrid implementation — §3's precedence order is a documented
  convention for flat-list promotion, not an implemented resolution
  algorithm.
- No change to `OCOMObject`'s schema.
- No change to the `Evidence` model — in particular, no `confidence`
  field added to it, despite §2 naming Evidence confidence as a real,
  currently unaddressed concept.
- No numeric confidence scoring algorithm — `confidence` values remain
  fixed labels, as everywhere else in this project.

## 6. Consequences — What This Implies for Existing Code

Named, not performed: `intelligence/classification.py`'s
`ClassificationProposal` and `apply_classification()` do not yet carry
`method`/`processor`, and `apply_classification()` has no conflict
awareness — it always appends new flat tags unconditionally, with no
check for whether an existing tag came from a lower-precedence method
that a new one should not silently join without going through §3's
promotion rule. A future task, not this document, would need to:

1. Add `method`/`processor` to `ClassificationProposal` and to the
   record `apply_classification()` writes.
2. Apply the `human > llm > rule-based` precedence rule when a new
   proposal's flat tags would conflict with (not merely add to) an
   existing classification, rather than the current
   append-if-not-present logic, which has no notion of "conflicting"
   versus "additional."

## 7. Decisions Recap

- Provenance for *who* added a piece of enrichment: `method` (fixed
  set) + `processor` (specific instance), both new keys inside the
  existing structured attribute record — no Core or Evidence change.
- Confidence is two different things: enrichment confidence (already
  tracked) and evidence confidence (a real concept, currently
  unaddressed anywhere in this codebase — named, not fixed).
- Conflicts are never auto-resolved for "truth" — every proposal is
  kept, fully attributed. A precedence order (`human > llm >
  rule-based`) governs only what gets promoted into the flat,
  resolver-visible `classification` list.
- History is append-only. No overwrite, no separate versioning system
  — the append-only list already is the version history.

## 8. Open Questions

1. **How is "which human" identified** without this becoming a privacy
   or governance problem this document isn't equipped to solve
   (§1)?
2. **Where does Evidence confidence eventually live**, given `Evidence`
   itself is frozen and this document explicitly declines to reopen
   it (§2)? A separate ADR, once the Memory/Confidence Model work this
   project has deferred since `core/evidence.py` was first written
   becomes real.
3. **Is `human > llm > rule-based` the right precedence**, or should
   it depend on the *specific* conflict (e.g. a `rule-based` result
   with `Evidence` from a verified internal document arguably
   deserves more weight than an `llm` result with none)? Untested —
   no real conflicting-enrichment scenario has occurred yet to check
   this against.
4. **Should the flat `classification` list ever carry more than the
   precedence winner**, honoring Meta/Classification.md.docx's
   "multiple classifications" allowance more literally, once there is
   real conflicting data to see whether that dilutes
   `IdentityResolver`'s signal in practice or not (§3)?
5. **`external` is unranked in the precedence order — should it be?**
   Deliberately left unresolved rather than guessed.

## Next Experiment

Introduce a **second method** into the existing, standalone
`intelligence/` package — not necessarily an LLM; even a hand-authored
`"human"`-method fixture correcting one of Classification Engine's own
existing outputs (e.g. overriding `Payment Manager`'s `domain` from
`"Finance"` to something a human reviewer prefers) would be enough —
and check three things concretely, the same way MILESTONE-003 checked
Identity Resolution rather than assuming it:

- Does the append-only structure in §4 actually stay readable and
  useful once a second entry exists for the same object, or does it
  need a way to query "what do we currently believe" that this
  document hasn't anticipated?
- Does the `human > llm > rule-based` precedence rule from §3 produce
  the outcome a person would actually expect, on a real (even if
  small) conflicting pair?
- Does anything downstream (`IdentityResolver`, `Registry`) behave
  differently once the flat `classification` list can change based on
  precedence rather than simple accumulation — this is the first time
  that list's contents would depend on more than "did a rule match,"
  and nothing has verified that assumption still holds.
