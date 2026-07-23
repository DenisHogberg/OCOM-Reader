# OCOM Classification Engine v0.1 — Design & Experiment

**Status:** Draft — design and hand-traced experiment only. No code exists for this component.
**Date:** 2026-07-23
**Builds on:** [OCOM Object Intelligence Layer v0.1 §5.1](OCOM-Object-Intelligence-v0.1.md#51-classification-engine), [ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-004](ADR-004-metadata-namespace-migration.md), [ADR-005](ADR-005-identity-resolution-signal-model.md), [MILESTONE-003](MILESTONE-003.md)
**Not touched by this document:** `core/object.py` (`OCOMObject.classification` stays `list[str]`, unchanged), `identity/resolver.py`, any LLM integration. No code is written by this document.

## Context

The order this project has actually followed, not a plan written in
advance of it:

```
Reader → Object → Evidence → Namespaces → Classification → Identity Resolution → Agent
```

Each step existed because the one before it produced a concrete,
evidenced gap — Evidence because raw metadata couldn't carry
provenance; namespaces because metadata couldn't carry both structured
data and comparison signal at once; and now Classification, because
[ADR-005](ADR-005-identity-resolution-signal-model.md) found that
`IdentityResolver`'s own signal model (Option C: classification as a
fallback for ambiguous identity matches) is only as good as the
classification data available to it — and today, almost none exists.
`LLMDocumentNormalizer` never populates `classification` at all.

This is the point ADR-005 flagged as premature to skip past: build the
thing that produces the fallback signal before recalibrating the
resolver that depends on it. This document is that component's design
— and, per this task, an experiment testing whether the simplest
possible version of it can actually produce something useful, before
any code is written.

## Responsibility Boundary

```
OCOM Object
      ↓
classification enrichment
      ↓
OCOM Object + structured classification
```

Exactly one object in, the same object out, with more of it populated.
This is the same boundary [OCOM-Object-Intelligence-v0.1.md §4](OCOM-Object-Intelligence-v0.1.md#4-responsibilities)
already committed the whole Object Intelligence Layer to; Classification
Engine is one component operating inside it, not a new boundary.

**Does not do**, each excluded for a reason already on record elsewhere
in this project, not invented here:

- **Identity resolution** — comparing objects to decide sameness stays
  `IdentityResolver`'s exclusive job
  ([OCOM-Identity-Resolution-v0.1.md §1](OCOM-Identity-Resolution-v0.1.md#1-responsibility)).
  Classification Engine looks at one object at a time and never
  compares two.
- **Object merging** — stays `Registry`'s job
  ([OCOM Agent v0.1 Design §6](OCOM-Agent-v0.1-Design.md#6-identity-resolution-strategy)).
- **Answer generation** — `AnswerComposer`'s job, untouched.
- **Source ingestion** — `Adapter`/`Normalizer`'s job
  ([ADR-001](ADR-001-normalizer-architecture.md)). Classification
  Engine only ever receives an already-normalized `OCOMObject`.

## Classification Model

The task's own example asks for a structured record:

```
classification:
[
  {
    "domain": "Marketing",
    "category": "Partner Management",
    "type": "Role"
  }
]
```

This is richer than what `OCOMObject.classification` can hold today —
that field is `list[str]` (Meta/Classification.md.docx describes a
fuller Classification concept with Identifier/Name/Type, but the
working model deliberately simplified it to flat strings, and this
document is explicitly barred from changing that). Reconciling the two
without a Core change means representing the same information at two
levels of detail, in two places that already exist:

- **Flat tags, on the existing top-level `classification: list[str]`**
  — e.g. `["Marketing", "Partner Management", "Role"]`. This is what
  `IdentityResolver` actually reads (per
  [ADR-003](ADR-003-metadata-semantic-boundary.md) /
  [ADR-005](ADR-005-identity-resolution-signal-model.md)) and must
  keep reading unchanged — the resolver has no reason to know this
  document exists.
- **The structured record, under `metadata["attributes"]["classification"]`**
  — using the field/value/evidence/confidence/timestamp shape already
  specified in
  [OCOM-Object-Intelligence-v0.1.md §5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment):

  ```python
  metadata["attributes"]["classification"] = [
      {
          "domain": "Marketing",
          "category": "Partner Management",
          "type": "Role",
          "evidence": ["evidence:oi-classification-affiliate-manager-01"],
          "confidence": "Medium",
          "timestamp": "2026-07-23T00:00:00Z",
      }
  ]
  ```

The flat list is a projection of the structured record, not a separate
decision — every tag that ends up in `classification` traces back to
one `domain`/`category`/`type` entry here.

**Open naming question, not resolved by this document:** whether `type`
in this record is meant to duplicate the object's `object_type`
(already `"Role"` in the task's own worked example) as a confirmation
signal, or to express something finer-grained
(`"Human Role"` vs. `"System Role"` vs. `"Process Role"`, all under a
coarser `object_type`). The experiment below produces `"Role"` either
way and does not need this resolved to proceed — flagged in Open
Questions rather than decided arbitrarily.

## Source of Classification

Per this task's instruction, chosen only on evidence already gathered
by this project, not fresh speculation:

- **Option A — Rule-based dictionary.** A small, explicit mapping from
  keywords to `domain`/`category`/`type` values.
- **Option B — LLM classification.** Reusing the `LLMClient` pattern
  already established in `LLMDocumentNormalizer`.
- **Option C — Hybrid.** A, escalating to B only when A is inconclusive.

**Decision: Option A**, unchanged from
[OCOM-Object-Intelligence-v0.1.md §5.1](OCOM-Object-Intelligence-v0.1.md#51-classification-engine)'s
prior reasoning: nothing has yet demonstrated Option A is insufficient,
because Option A had never actually been traced against a concrete
example before this document. The Experiment section below is that
trace — this document does not just reassert the prior decision, it
tests it for the first time.

## Evidence Requirement

Every classification value must carry `value` / `source` / `confidence`
/ `timestamp` (this task's own requirement), which is exactly the
structured-attribute shape already adopted in the Classification Model
section above.

**Where Evidence itself is stored:** the existing `OCOMObject.evidence`
list — not a separate enrichment record. This was already decided in
[OCOM-Object-Intelligence-v0.1.md §5.4](OCOM-Object-Intelligence-v0.1.md#54-evidence-model-integration)
and is reaffirmed, not re-litigated, here: a new `Evidence` entry per
classification action, `source="object-intelligence:classification-engine"`,
`reference` pointing at the upstream `Evidence.identity` that justified
it, `excerpt` stating the inference in human-readable form (e.g.
`"Classified as 'Marketing' based on 'affiliate' keyword"`). A separate
"Object Intelligence Record" was already explicitly rejected as an
option for this whole layer
([OCOM-Object-Intelligence-v0.1.md §10, Q2](OCOM-Object-Intelligence-v0.1.md#10-non-goals));
nothing in this document reopens that.

## Experiment

**Method:** hand-traced, not executed. No code exists for this
component; the point is to check whether the simplest possible version
of Option A can plausibly work before writing any.

**Input**, as given by the task, fleshed out into a realistic
`OCOMObject` shape (consistent with what a Normalizer already
produces):

```
identity:    role:affiliate-manager
object_type: Role
metadata:
  identity: { "name": "Affiliate Manager" }
evidence:
  - source: filesystem-documentation
    reference: AffiliateManager.md
    excerpt: "manages affiliate relationships and commission payouts"
classification: []          ← the gap this component exists to fill
```

**A minimal rule-based dictionary**, small enough to state in full:

| Keyword found in `metadata["identity"]` or `evidence[].excerpt` | Proposes |
|---|---|
| `"affiliate"` | `domain: "Marketing"`, `category: "Partner Management"` |
| `"partner"` | `category: "Partner Management"` |
| word ending in `"manager"` as part of the name | `type: "Role"` |

**Trace:**

1. Tokenize `metadata["identity"]["name"]` = `"Affiliate Manager"` →
   `{"affiliate", "manager"}`.
2. `"affiliate"` matches the dictionary → propose
   `domain="Marketing"`, `category="Partner Management"`.
3. `"Manager"` as a name suffix matches the dictionary → propose
   `type="Role"`.
4. Result: `type=Role, domain=Marketing, category=Partner Management`.

**This matches the task's expected output exactly, without reading the
`Evidence` excerpt at all** — the name alone was sufficient for this
particular example. That the excerpt (`"manages affiliate
relationships..."`) would have reinforced the same result if used is a
secondary finding, not the load-bearing one.

### Question 1 — Can useful classification be obtained without an LLM?

**Yes, for this example, confirmed by the trace above — not assumed.**
A three-rule dictionary reproduced the exact expected output. This is
the first time Option A's viability has been checked against a
concrete case rather than asserted from a prior document.

### Question 2 — What data does the object need?

At minimum: a `metadata["identity"]` value containing vocabulary the
dictionary recognizes. The `Evidence` excerpt was not required for
this trace to succeed, though it would help recall in cases where the
name alone is too generic (see failure modes below).

One deliberate distinction from `IdentityResolver`'s situation: reading
free-text `Evidence.excerpt` content here is **not** the same risk
[MILESTONE-003](MILESTONE-003.md) found for `IdentityResolver`.
`IdentityResolver` was comparing two arbitrary free-text blobs to each
other, where shared vocabulary between two *unrelated* objects produced
a false `MATCH`. Classification Engine matches free text against a
*fixed, curated dictionary*, not against another object's text — there
is no second object whose incidental phrasing could be confused for
this one's. Free-text input is a legitimate signal here in a way it
was not there.

### Question 3 — Where does rule-based break?

Not hypothetically — each of these is a concrete extension of the
example above, not a new scenario invented to sound cautious:

- **Synonym blindness.** `"Partner Success Lead"` or `"Channel
  Relationship Manager"` — plausibly the same real-world category of
  role as "Affiliate Manager" — trigger none of the three rules above,
  because none of their words are in the dictionary. This is the exact
  same class of limitation [MILESTONE-003](MILESTONE-003.md) already
  proved for lexical identity matching, now surfacing in classification
  instead: a dictionary only recognizes the vocabulary it was given.
- **Keyword ambiguity.** `"Payment Manager"` — a system/software
  component in some sources, a person's job title in others — would
  trigger the same `"manager"` → `type: "Role"` rule regardless, with
  no way for a single-keyword rule to use context to tell those apart.
- **Incomplete output when vocabulary is generic.** An object named
  just `"Manager"`, with no domain-specific word at all, produces only
  `type: "Role"` — no `domain`, no `category`. This is an honest
  partial result, not a wrong one, but it means dictionary coverage
  directly bounds how *complete* a classification can be, not just how
  correct it is.
- **Maintenance burden.** Every new domain or category this system
  needs to recognize requires a human to add a rule. This does not
  self-improve or generalize to a domain nobody anticipated —
  restating [OCOM-Object-Intelligence-v0.1.md §5.1](OCOM-Object-Intelligence-v0.1.md#51-classification-engine)'s
  original caution about Option A, now grounded in an actual traced
  failure mode rather than a general worry.

## Non-Goals

- No code — nothing in this document is implemented.
- No change to `OCOMObject` — `classification` stays `list[str]`.
- No change to `identity/resolver.py` — it continues reading flat
  `classification` and `metadata["identity"]` exactly as ADR-003/005
  left it.
- No LLM integration — Option B is not built, per the Option A
  decision above.
- No confidence-scoring algorithm — `confidence` values in the
  structured record are fixed labels (e.g. `"Medium"` for a
  single-keyword match), not a computed score, matching every prior
  use of `confidence` in this project.
