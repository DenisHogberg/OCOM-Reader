# MILESTONE-003: Identity Resolution — Experiment Findings

**Date:** 2026-07-23
**Status:** Frozen — this document closes the Identity Resolution experiment phase and sets the next architectural candidate before any further Agent or Resolver work.
**Builds on:** [OCOM Identity Resolution v0.1](OCOM-Identity-Resolution-v0.1.md), [ADR-002](ADR-002-agent-vertical-slice-boundaries.md), [MILESTONE-002](MILESTONE-002.md)

## 1. What Was Tested

Two experiments, both against `identity/resolver.py`
(`IdentityResolver`, Option B from
[OCOM-Identity-Resolution-v0.1.md §3](OCOM-Identity-Resolution-v0.1.md#3-decision-model):
`object_type` gate + word-overlap over `metadata` and `classification`,
stdlib only). The resolver's code did not change between or during
either experiment — only its input did.

- **Rule-based `IdentityResolver` v0.1**, exercised against four
  scenarios designed to probe its core outcomes (`test_identity_resolver_experiment.py`):
  exact match, clearly different objects, ambiguous-but-related
  objects, and the evidence-absence case.
- **Minimal objects** — `identity`, `object_type`,
  `metadata["name"]` only, nothing else populated
  (`test_identity_object_representation_experiment.py`, Variant A).
- **Structured objects** — the same minimal object plus
  `classification`, `relationships`, `lifecycle_state`, and `evidence`,
  with no free-text field added (Variant B′).
- **Free-text enrichment** — Variant B′ plus one additional free-text
  `metadata` attribute (`"responsibility"`), matching the enriched-object
  example given for this experiment, tested with two independently
  plausible phrasings of the same role pair.

All of it run against two role pairs chosen to have a known right
answer: *Affiliate Manager / Partner Manager* (related, plausibly the
same or adjacent roles) and *Affiliate Manager / Payment Manager*
(unrelated).

## 2. Confirmed

- **Minimal object representation is insufficient.** Not a
  hypothesis — a measured fact. With only a bare name, *Affiliate
  Manager vs. Partner Manager* and *Affiliate Manager vs. Payment
  Manager* produced the exact same outcome (`NEW`) at the exact same
  score (0.20) and the exact same `reasoning` string. The resolver had
  no way to tell a related pair from an unrelated one, because nothing
  in the object distinguished them.
- **Structured attributes measurably improve resolution quality, with
  no algorithm change.** Adding `classification` (plus `relationships`,
  `lifecycle_state`, `evidence` — all fields the schema already had)
  moved *Affiliate/Partner* to `UNCERTAIN` (0.60) while
  *Affiliate/Payment* stayed at `NEW` (0.20) — a clean, reproducible
  0.40 separation, using the same resolver code as the minimal-object
  run above.
- **Evidence is mandatory for `MATCH`.** Confirmed again in this
  round, consistent with [OCOM-Identity-Resolution-v0.1.md §4](OCOM-Identity-Resolution-v0.1.md#4-evidence-requirements):
  a candidate/existing pair with identical metadata and classification
  but missing `Evidence` on one side is downgraded to `UNCERTAIN`, never
  `MATCH`, regardless of how high the underlying similarity score is.
- **Free-text cannot be used as a direct similarity signal without
  separate handling.** This is the sharpest finding of the round: two
  equally realistic phrasings of the same `responsibility` attribute,
  for the same role pair, with identical `classification` and every
  other field held constant, produced *different outcomes* —
  `NEW` (0.48, just under threshold) in one phrasing, and a **false
  `MATCH`** (1.00) in the other, purely because that phrasing happened
  to reuse both role names' vocabulary in both descriptions. Feeding
  raw free text into the same word-overlap scorer used for structured
  fields does not add reliable signal — it adds a wording-dependent
  failure mode, including the worst kind (a confident wrong answer,
  not just an uncertain one).

## 3. New Architectural Conclusion: Object Enrichment Layer

The experiment points at a layer that does not exist yet, sitting
*before* Identity Resolution rather than replacing it:

```
Raw OCOM Object
        ↓
   Enrichment
        ↓
Structured OCOM Object
        ↓
Identity Resolution
```

Its responsibility, based directly on what was confirmed in §2: take
an `OCOMObject` as produced by a `Normalizer` — which today may carry
little beyond `metadata["name"]`-equivalent data (e.g.
`LLMDocumentNormalizer` does not populate `classification` at all) —
and ensure it carries the *structured* fields that were shown to
matter: `classification` at minimum, and plausibly `relationships` /
`lifecycle_state` where a source can support them. What it must
**not** do, per §2's last finding, is dump unstructured descriptive
text into the same fields a similarity scorer reads — if free text is
enriched in, it needs its own treatment, not direct inclusion in a
word-overlap comparison.

This is a candidate, not a decision to build: no interface, no module
boundary, no dependency on `IdentityResolver`'s internals has been
designed yet. That is future work, out of scope for this document.

## 4. Not Doing (Yet)

Explicitly not being added as a result of this milestone:

- **LLM Resolver** — the free-text failure mode in §2 looked, at
  first glance, like a case for LLM-assisted resolution. It turned out
  to be a data-representation and scoring-design problem instead:
  structured enrichment alone (no LLM) already produced the correct
  `UNCERTAIN`/`NEW` split. Nothing in this experiment demonstrated a
  case that structured enrichment cannot fix.
- **Embeddings**
- **Vector search**

None of these are ruled out permanently — they are ruled out *for
now*, because the experiment has not yet produced a case where a
better-structured object still fails to resolve correctly. Revisiting
this is only warranted once Object Enrichment Layer exists and a real
case survives it unresolved — the same discipline this project has
applied at every prior milestone: build the next layer because a
concrete result demanded it, not because it might eventually be
needed.
