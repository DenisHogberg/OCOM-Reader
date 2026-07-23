# OCOM Object Intelligence Layer v0.1 — Design

**Status:** Draft — design only, nothing in this document has been implemented.
**Date:** 2026-07-23
**Builds on:** [MILESTONE-003](MILESTONE-003.md) (Identity Resolution Experiment Findings), [OCOM Identity Resolution v0.1](OCOM-Identity-Resolution-v0.1.md), [OCOM Agent v0.1 Design](OCOM-Agent-v0.1-Design.md)
**Frozen by this design (no changes proposed, none needed):** `core/`, `interfaces/`, `storage/`, `agent/`, `identity/`. Any change to those requires its own ADR.
**Superseded content (added by [Architecture Consistency Cleanup v0.1](Architecture-Status-v0.1.md)):** §5.4's worked example originally showed the structured classification record as `metadata["attributes"]["classification_confidence"][tag]`. [OCOM-Classification-Engine-v0.1.md](OCOM-Classification-Engine-v0.1.md), written after this document, adopted a different, incompatible shape — `metadata["attributes"]["classification"] = [...]` (a list of records) — which is the one actually implemented (`intelligence/classification.py`) and the one [OCOM-Enrichment-Provenance-v0.1.md](OCOM-Enrichment-Provenance-v0.1.md) and [ADR-006](ADR-006-classification-lifecycle-and-human-override.md) build on. The example below is corrected to match. §5.1–§5.3, §6–§11 remain otherwise accurate as design (Relationship Intelligence and Attribute Enrichment are unimplemented, exactly as this document already says).

## 1. Purpose

[MILESTONE-003](MILESTONE-003.md) closed with a specific, evidence-backed
conclusion: `IdentityResolver` cannot compensate for a thinly
represented object, but a *structurally* richer object — same schema,
more of it populated — resolves correctly with no algorithm change.
Nothing currently in this codebase is responsible for making that
richer representation exist. `Normalizer`s produce whatever a single
source happens to yield (today, often close to MILESTONE-003's
"Variant A": a name and not much else); nothing sits between that and
`IdentityResolver` to close the gap.

**Object Intelligence Layer v0.1 is that missing step.** Its purpose is
to turn a `Raw OCOM Object` into a `Reasoning-ready OCOM Object` —
one with the structured `classification`, `relationships`, and
attributes that MILESTONE-003 proved matter — without changing what an
`OCOMObject` *is*. It makes existing objects more complete. It does not
make the system "smarter" in any general sense, and it does not decide
anything MILESTONE-003 didn't already hand it good reason to attempt.

## 2. Problem Statement

Three findings from MILESTONE-003, restated as a gap rather than a
result:

1. **A `Normalizer`'s minimal output is exactly MILESTONE-003's Variant
   A.** `LLMDocumentNormalizer` (the only LLM-based Normalizer that
   exists) populates `metadata["concept"]` and nothing else structural
   — no `classification`, no `relationships`. It was never supposed to
   do more: per [ADR-001](ADR-001-normalizer-architecture.md), a
   Normalizer's job is translating one raw record into one `OCOMObject`,
   not analyzing it against everything else the system knows.
2. **`IdentityResolver` cannot be the place this gets fixed either.**
   Per [OCOM-Identity-Resolution-v0.1.md §1](OCOM-Identity-Resolution-v0.1.md#1-responsibility),
   its responsibility is candidate comparison and decision-making, not
   extraction — it was designed, deliberately, to consume structure it
   does not produce.
3. **Naively adding unstructured text does not fill the gap — it
   actively breaks the one signal that already worked.**
   MILESTONE-003's sharpest finding: free text dropped into `metadata`
   and read by the same word-overlap scorer as everything else produced
   a *false* `MATCH`, not just an unhelpful one.

Nothing existing is positioned to do this work, and doing it carelessly
is worse than not doing it. That is the specific gap this layer fills.

## 3. Architecture Overview

Object Intelligence sits downstream of `Normalizer`, upstream of
`IdentityResolver` — a new stage in the ingestion path, not a
replacement of any existing one:

```
                READER (unchanged)                    IDENTITY (unchanged)
Source → Adapter → Raw Data → Normalizer → OCOMObject → IdentityResolver → Registry/Storage
                                                │                ▲
                                                │                │
                                                ▼                │
                                    ┌───────────────────────┐    │
                                    │  OBJECT INTELLIGENCE   │────┘
                                    │      (this design)      │
                                    │                          │
                                    │  Attribute Enrichment    │
                                    │         ↓                │
                                    │  Classification Engine   │
                                    │         ↓                │
                                    │  Relationship Intelligence│
                                    └───────────────────────┘
```

It takes exactly one `OCOMObject` in and returns exactly one
`OCOMObject` out — same identity, same schema, more of its existing
fields populated, more `Evidence` attached. It never receives or
returns anything else, and it never looks at more than one object's
own data at a time (comparing objects to each other is
`IdentityResolver`'s job — see §9).

New code for this layer would live in its own package, parallel to
`identity/` and `agent/`, not inside either:

```
src/ocom_reader/
  core/            unchanged
  interfaces/      unchanged
  storage/         unchanged
  agent/           unchanged
  identity/        unchanged
  intelligence/    new — not implemented by this document
```

## 4. Responsibilities

**In scope:**

- **Classification enrichment** — proposing `classification` tags
  (domain, category, role, capability) for the existing
  `classification: list[str]` field.
- **Relationship discovery** — proposing `Relationship` entries for the
  existing `relationships: list[Relationship]` field, subject to the
  resolution constraint in §5.2.
- **Structured attribute extraction** — deriving named, evidenced,
  confidence-scored values, stored under the existing `metadata` field
  (§5.3) — never as bare free text.
- **Object capability detection** — identifying what an object can do
  or provide, per the OCOM Capability concept
  (Meta/Capability.md.docx: "the ability of an Object to perform,
  provide, enable, or support"). `OCOMObject`'s working model has no
  dedicated `capabilities` field (Capabilities are explicitly listed as
  an optional characteristic not yet implemented — see
  `core/object.py`'s own docstring), so v0.1 represents a detected
  capability as a `classification` tag or a structured attribute, not
  a new field.
- **Semantic normalization** — deriving a canonical form of an
  object's name/label as a structured attribute (e.g.
  `metadata["attributes"]["normalized_name"]`), so that later
  consumers have a stable string to compare instead of whatever
  surface form a source happened to use. This does not change
  `metadata["concept"]` or any field a Normalizer already writes — it
  adds a new, separately-evidenced attribute alongside it.

**Explicitly out of scope:**

- **Identity Resolution** — Object Intelligence analyzes one object.
  It never compares two objects to each other or decides whether they
  are the same thing. That line is absolute: the moment a component
  needs a second object to make a decision, it is doing
  `IdentityResolver`'s job, not this layer's.
- **Answer generation** — `AnswerComposer`'s job, untouched.
- **Source ingestion** — `Adapter`/`Normalizer`'s job, untouched. Object
  Intelligence never reads a source directly; it only ever receives an
  already-normalized `OCOMObject`.
- **Write-back** — no source system is ever written to. This layer
  inherits the same boundary already stated for the whole Agent side of
  this project ([OCOM Agent v0.1 Design §8](OCOM-Agent-v0.1-Design.md#8-security-boundaries)).
- **Autonomous decisions** — every enrichment is a *proposal* attached
  with its own evidence and confidence, not a silent, unexplained
  mutation. Nothing here changes `lifecycle_state`, `owner`, or
  `governance` — those remain human/governance-driven fields this layer
  does not touch.

## 5. Components

### 5.1 Classification Engine

**Question: how does an object get `domain` / `category` / `role` /
`capability` tags?**

Two viable approaches, evaluated rather than defaulting to the more
capable one — the same discipline
[OCOM-Identity-Resolution-v0.1.md §3](OCOM-Identity-Resolution-v0.1.md#3-decision-model)
already applied to `IdentityResolver`:

- **Rule-based / controlled-vocabulary lookup.** A small, explicit
  mapping from keywords found in an object's `metadata` and `Evidence`
  excerpts to classification tags (e.g. a title containing "Manager"
  → `"Human Role"`; containing "Affiliate" → `"Partner Management"`).
  Zero new dependencies, fully deterministic, every tag traceable to
  the exact keyword that produced it.
- **LLM-assisted classification**, reusing the `LLMClient` injection
  pattern already established in `LLMDocumentNormalizer` — read an
  object's evidence excerpts and ask for likely classification tags
  with structured, validated output.

**v0.1 decision: rule-based only.** Not because the LLM option is
wrong in principle — `LLMDocumentNormalizer` already proves the
pattern works — but because nothing yet demonstrates rule-based
classification is insufficient, and MILESTONE-003's own context note
is explicit: *"LLM-based Identity Resolution пока не обоснован
экспериментально."* The same standard applies here: no experiment has
been run against Classification Engine specifically, so this document
does not default to the more capable option before one exists. This
mirrors [OCOM-Identity-Resolution-v0.1.md §3](OCOM-Identity-Resolution-v0.1.md#3-decision-model)'s
own Option D deferral.

Worked example, matching the task's own:

```
Affiliate Manager
  metadata: {"name": "Affiliate Manager"}
  evidence excerpt: "manages affiliate relationships and commission payouts"

Classification Engine proposes:
  - "Marketing"            (keyword: "affiliate")
  - "Partner Management"   (keyword: "affiliate" + "manages relationships")
  - "Human Role"           (keyword: "Manager" as a title suffix)
```

Each proposed tag is appended to `classification` and backed by a new
`Evidence` entry (§7) — never added silently.

### 5.2 Relationship Intelligence

**Question: how are relationships created, and what types are
needed?**

v0.1 relationship vocabulary (fixed, small, matching
[OCOM Agent v0.1 Design's](OCOM-Agent-v0.1-Design.md) rejection of a
"complex ontology engine"): `owns`, `manages`, `depends_on`,
`related_to`, `implements`.

**The hard constraint this component must respect:** `Relationship.
target_id` is a string that is supposed to identify a real Object
(Meta/Reference.md.docx: *"A Reference should point to an identifiable
Object"*; *"Reference Integrity should be periodically validated"*).
Relationship Intelligence must never invent a `target_id` from a bare
mention in text — "this document mentions a 'Partner Manager' role"
is not the same claim as "this object relates to the specific,
already-known object whose identity is `role:partner-manager`."

This creates a **one-way dependency on Identity Resolution having
already run for the mentioned target**: Relationship Intelligence can
only commit a `Relationship` entry once whatever it detected as a
plausible target has already been resolved to a real, existing
`identity` — by `IdentityResolver`, elsewhere, not by this component.
v0.1 Relationship Intelligence's scope is therefore narrower than
Classification Engine's: it can propose relationships only where the
target is unambiguous (e.g. a raw source that names another object's
identity directly), and must not fabricate a `target_id` from a fuzzy
text mention. See §9 for why this is a two-way dependency at the
system level even though this component's own dependency runs one way.

### 5.3 Structured Attribute Enrichment

**Question: what additional fields are allowed?**

None, structurally — no field is added to `OCOMObject`. What this
component defines is the *shape* every enriched value must take inside
the existing `metadata` dict, under a dedicated, namespaced key so it
is never confused with whatever a Normalizer already wrote there:

```python
metadata["attributes"] = {
    "<field_name>": {
        "value": ...,
        "evidence": ["<Evidence.identity>", ...],  # never a bare string
        "confidence": "Low" | "Medium" | "High" | "Verified",  # OCOM Confidence levels, reused
        "timestamp": "<ISO-8601>",
    },
    ...
}
```

This is a direct, deliberate response to MILESTONE-003's finding: a
bare string in `metadata` (e.g. `metadata["responsibility"] = "..."`)
is what produced the false `MATCH`. A structured record under
`metadata["attributes"]` is auditable and evidenced the way the rest of
this project already requires — but see §9 for why this shape alone
does **not** yet protect `IdentityResolver`'s current scorer from
re-contaminating itself on this same data.

### 5.4 Evidence Model Integration

Every action any of the three components above takes — every proposed
classification tag, every committed relationship, every structured
attribute — produces exactly one new `Evidence` entry on the object it
enriched. No `Evidence` model field changes; the convention is entirely
in how existing fields are used:

- **`source`** is set to a namespaced string identifying which
  component produced it — `"object-intelligence:classification-engine"`,
  `"object-intelligence:relationship-intelligence"`,
  `"object-intelligence:attribute-enrichment"` — distinct from a
  source like `"filesystem-documentation"`, which names an origin
  *system*. This lets anything reading `Evidence.source` later tell
  "observed directly from a source" apart from "derived by internal
  analysis" without a new field.
- **`reference`** points at the *upstream* `Evidence.identity` that
  justified the derivation (the classification "Partner Management"
  references the `Evidence` entry whose excerpt contained "affiliate"),
  not a synthetic or self-referential pointer. This keeps the
  derivation chain traceable back to a real observation, per Meta/
  Reference.md.docx's integrity requirement — an inference that cannot
  name what it was inferred from is not the kind of grounding this
  project has required anywhere else.
- **`captured_at`** is the enrichment run's own timestamp, not copied
  from the upstream `Evidence`.
- **`excerpt`** is a short, human-readable statement of the inference
  itself (e.g. `"Classified as 'Partner Management' based on 'affiliate'
  keyword"`), not a copy of the source text.

Worked example, matching the task's own — **canonical form, as corrected
per the note at the top of this document.** The structured record is a
list under `metadata["attributes"]["classification"]`, each entry
carrying its own `domain`/`category`/`type`, not a dict keyed by tag
name under `classification_confidence` as an earlier draft of this
example showed:

```
Added classification: "Partner Management"

Evidence:
  identity:    evidence:oi-classification-affiliate-manager-01
  source:      object-intelligence:classification-engine
  reference:   evidence:object-md-excerpt-04        (the upstream Evidence this was derived from)
  captured_at: 2026-07-23T00:00:00Z
  excerpt:     "Classified as 'Partner Management' based on 'affiliate' keyword"

metadata["attributes"]["classification"]:
  - domain:      "Marketing"
    category:    "Partner Management"
    type:        null
    evidence:    ["evidence:oi-classification-affiliate-manager-01"]
    confidence:  "Medium"
    timestamp:   2026-07-23T00:00:00Z
```

## 6. Data Flow

```
Normalizer output (Raw OCOM Object)
        ↓
Attribute Enrichment   — extract structured, evidenced facts from metadata/evidence
        ↓
Classification Engine  — propose classification tags, using facts extracted above
        ↓
Relationship Intelligence — propose relationships, only to already-resolved identities
        ↓
Reasoning-ready OCOM Object (same identity, same schema, richer classification/
                              relationships/metadata, additional Evidence)
        ↓
IdentityResolver (unchanged)
```

**On the fixed order (Attributes → Classification → Relationships):**
this is a recommendation, not a proven necessity — flagged as a
hypothesis in §11. The reasoning: Classification Engine's worked
example above already assumes a structured fact ("manages affiliate
relationships") is available to justify a tag; producing that fact is
Attribute Enrichment's job, so it runs first. Relationship
Intelligence runs last because resolving a target identity may itself
benefit from the object already carrying richer classification (two
objects sharing a classification tag is exactly the kind of signal
`IdentityResolver` already uses).

This is composition, not a monolith: each component is independently
callable and independently testable (as `identity/resolver.py` already
is, with no dependency on `agent/` or `Storage`). The fixed order is
how a thin orchestrator would call them by default, not a constraint
baked into any one component reaching into another's internals.

## 7. Evidence Handling

Covered in detail in §5.4. Summarized: **enrichment without evidence is
not enrichment this layer performs.** Every proposed classification
tag, attribute, or relationship carries its own `Evidence` entry,
sourced back to whatever upstream `Evidence` justified it, using the
`source` field to mark it as derived rather than observed. This is the
same "no ungrounded claim" discipline already enforced by
`AnswerComposer` ([ADR-002](ADR-002-agent-vertical-slice-boundaries.md))
and by `IdentityResolver`'s evidence-gated `MATCH`
([OCOM-Identity-Resolution-v0.1.md §4](OCOM-Identity-Resolution-v0.1.md#4-evidence-requirements)),
applied a third time, to a third layer. If an enrichment action cannot
name the `Evidence` it is based on, it does not get to run — there is
no confidence-free fallback path anywhere in this component.

## 8. Interaction with Identity Resolver

`identity/resolver.py` is not modified by this design and is not
expected to need to be, for the parts of MILESTONE-003 already proven:
richer `classification` is read by the existing resolver exactly as it
is today, with no changes, and produces exactly the improvement
MILESTONE-003 measured.

**What this design does not solve, and states plainly rather than
implying it does:** `metadata["attributes"]`, as specified in §5.3, is
still a value inside `metadata`, and `IdentityResolver._metadata_tokens()`
today stringifies and tokenizes *every* value in `metadata` without
distinguishing a structured, confidence-scored attribute record from
anything else. A nested dict under `metadata["attributes"]` will still
be turned into a string and tokenized by the current, unmodified
resolver — meaning the structured shape in §5.3 solves the *auditability*
problem MILESTONE-003 raised, but does **not**, by itself, solve the
*scorer contamination* problem also raised there. Making
`IdentityResolver` aware of the `attributes` namespace (e.g. excluding
it from raw word-overlap scoring, or scoring it separately with its own
confidence-weighted logic) is a change to `identity/resolver.py`, which
this document is not authorized to make and does not propose. It is
named here as the specific, concrete follow-up this design creates —
see §11.

**Relationship Intelligence's dependency runs the other way, and is
circular at the system level, not just one-directional as stated in
§5.2:** Relationship Intelligence needs `IdentityResolver` to have
already resolved a mentioned target before it can commit a
`Relationship`; `IdentityResolver`'s own matching, per MILESTONE-003,
improves when an object already has richer `relationships`. Neither
component can be said to strictly run "before" the other in a single
pass — this is named as an open question (§11), not resolved by
picking an arbitrary order.

## 9. Interaction with Agent

`agent/` is not modified by this design. Two indirect effects follow
from Object Intelligence existing, without any code in `agent/`
changing:

- **`EvidenceAggregator`/`AnswerComposer`** ([OCOM Agent v0.1 Design](OCOM-Agent-v0.1-Design.md))
  will see more `Evidence` per object once enrichment runs, some of it
  marked `source="object-intelligence:*"` rather than an original
  ingestion source. `AnswerComposer` does not currently distinguish
  observed from derived evidence when composing an answer — it treats
  every `Evidence` entry the same. Whether it *should* start
  distinguishing them (e.g. phrasing a derived classification
  differently from a directly quoted excerpt) is not decided here —
  see §11.
- **`ObjectRegistry.find_candidates()`**'s keyword search
  ([ADR-002](ADR-002-agent-vertical-slice-boundaries.md) already named
  this as a placeholder) reads `object_type`, `classification`, and
  `metadata` values exactly like `IdentityResolver` does. Richer
  `classification` from this layer improves `Registry` search results
  as a side effect, with zero changes to `agent/registry.py` — the
  same reuse-without-modification relationship this design has with
  `identity/resolver.py`.

## 10. Non-Goals

Restated from the task, plus what this document adds on inspection:

- LLM Resolver (for Identity Resolution) — still not justified; nothing
  in this design changes that finding.
- Embeddings
- Vector search
- Identity Resolution, Answer generation, Source ingestion, Write-back,
  Autonomous decisions (§4)
- Any change to `core/`, `interfaces/`, `storage/`, `agent/`, or
  `identity/`
- A new persisted "Object Intelligence View" separate from the
  `OCOMObject` itself — ruled out explicitly in §5.2/architectural
  question 2 below, not merely unaddressed
- A general-purpose ontology or taxonomy engine — the relationship
  vocabulary (§5.2) is a fixed, small, named list, not an extensible
  type system
- Automatic resolution of conflicting enrichment proposals (e.g. two
  components proposing contradictory classification) — surfaced via
  multiple `Evidence`-backed entries, the same "don't adjudicate,
  surface" stance already taken in
  [OCOM Agent v0.1 Design §7](OCOM-Agent-v0.1-Design.md#7-evidence-handling)
- A confidence *scoring algorithm* — `confidence` values in §5.3 are
  simple, fixed labels (reusing the existing OCOM Confidence levels),
  not a computed score, matching how `LLMDocumentNormalizer` already
  treats confidence

### Architectural Questions — Answered

**1. Pipeline or independent processors?** Both, at different levels:
independently-callable, independently-testable components (§6),
composed by a thin orchestrator in a fixed default order — the same
shape already used for `Adapter`/`Normalizer`/`Storage` and for
`Query`/`Registry`/`EvidenceAggregator`/`AnswerComposer`. Not a single
monolithic function, not fully decoupled siblings with no defined
relationship either — the order in §6 is a stated hypothesis, not
enforced coupling between components.

**2. Where does the result live?** Inside the existing `OCOMObject` —
`classification`, `relationships`, and `metadata["attributes"]`
directly. A separate "Object Intelligence View" is explicitly rejected
for v0.1: it would mean a second persisted representation of the same
object, which is both a new persistence concept `storage/` was never
designed for and arguably a violation of "Object Intelligence does not
create a new object" in spirit if not in name. A *computed, read-time*
view (comparable to `agent/`'s `UnifiedObjectView`) remains conceivable
later without conflicting with this decision, since it would persist
nothing new — but it is not part of this design.

**3. When does enrichment run?** At ingestion time, between
`Normalizer` output and `IdentityResolver` input (§3) — this is the
only trigger this design specifies. On-demand re-enrichment triggered
by `Agent` (e.g. lazily enriching a thin, older object when a query
needs it) is a real, plausible future capability, but introduces
staleness/re-trigger questions this document does not attempt to
answer — left open (§11) rather than decided by default.

## 11. Open Questions

1. **The `attributes` / scorer contamination gap (§8) is the most
   concrete unresolved item in this document.** Structured attribute
   records do not automatically protect `IdentityResolver`'s current
   word-overlap scoring from the exact failure mode MILESTONE-003
   found with free text. Closing this requires a change to
   `identity/resolver.py`, out of scope here, and deserves its own
   experiment before that change is made — not a guess about which
   fields to exclude from scoring.
2. **The Relationship Intelligence ↔ Identity Resolution ordering is
   circular at the system level (§8).** No single-pass pipeline order
   resolves both directions cleanly. Whether this needs multiple
   ingestion passes, a deferred/pending relationship state, or
   something else is unanswered.
3. **Is Attributes → Classification → Relationships actually the right
   default order (§6)?** Stated as a reasoned hypothesis, not
   validated against any real object.
4. **Should `AnswerComposer` eventually distinguish observed from
   derived `Evidence` (§9)?** The `source` naming convention in §5.4
   makes this possible without a schema change, but nothing currently
   consumes that distinction.
5. **Should enrichment ever run lazily, on Agent request, in addition
   to at ingestion time (architectural question 3)?** Not decided;
   named as future scope only.
6. **Are fixed confidence labels enough, or does Structured Attribute
   Enrichment need its own validation experiment**, the way
   `IdentityResolver`'s decision model got one before this document was
   written? Not tested — this document specifies a shape, not a
   confidence-assignment method.
