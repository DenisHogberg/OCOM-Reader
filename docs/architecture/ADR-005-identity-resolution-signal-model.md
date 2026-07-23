# ADR-005: Identity Resolution Signal Model

**Status:** Accepted
**Date:** 2026-07-23
**Applies to:** the semantics `identity/resolver.py` is expected to implement — not its numeric weights or thresholds, which this ADR deliberately does not touch
**Builds on:** [ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-004](ADR-004-metadata-namespace-migration.md), [MILESTONE-003](MILESTONE-003.md), [OCOM Identity Resolution v0.1](OCOM-Identity-Resolution-v0.1.md)
**Not touched by this ADR:** `core/`, `interfaces/`, `storage/`, `agent/`, and the actual numeric constants in `identity/resolver.py` (`MATCH_THRESHOLD`, `UNCERTAIN_THRESHOLD`, `METADATA_WEIGHT`, `CLASSIFICATION_WEIGHT`). This document decides what those numbers are supposed to *mean*; changing them is separate, future work.

## Context

Now that `identity/resolver.py` reads only `metadata["identity"]`
(ADR-003/ADR-004, implemented), a question those two documents didn't
have to answer becomes unavoidable: **what is `classification` actually
for in a MATCH decision, and what happens to an object that doesn't
have any?**

This is not hypothetical. `LLMDocumentNormalizer` — the only Normalizer
in this codebase that does anything resembling semantic identity work
— never populates `classification` at all
(`src/ocom_reader/normalizers/llm_document_normalizer.py`, current
implementation). Meanwhile, the resolver's existing, unmodified
weighting (`METADATA_WEIGHT=0.6`, `CLASSIFICATION_WEIGHT=0.4`,
`MATCH_THRESHOLD=0.9`) already has a real, unexamined consequence: a
**perfect** `metadata["identity"]` match, alone, tops out at a combined
score of `0.6 * 1.0 = 0.6` — below `MATCH_THRESHOLD`. Under the current
arithmetic, `MATCH` is *mathematically unreachable* without some
classification overlap, for any pair of objects, no matter how
identical their names are.

Nobody decided this. It fell out of numbers chosen to make
[MILESTONE-003](MILESTONE-003.md)'s specific test fixtures behave
correctly, not from an examined claim about what `classification`
means for identity resolution. That is exactly the situation this
project has repeatedly flagged as dangerous: tuning coefficients before
their semantics are decided. This ADR decides the semantics first.

## 1. Identity Signals

What can legitimately participate in an identity decision, and what
each one's role is:

| Signal | Current role | Kept for v0.1? |
|---|---|---|
| `object_type` | Hard gate — mismatch is immediate `NEW`, never scored | Yes, unchanged |
| `metadata["identity"]` (name, aliases) | Weighted similarity signal | Yes, unchanged |
| `classification` | Weighted similarity signal | Yes — role clarified in §2 |
| `evidence` (presence) | Binary gate on `MATCH` eligibility | Yes — role clarified in §3 |
| `relationships` | Not read at all | **No — explicitly deferred, not silently omitted** |

`object_type` remains a categorical gate, not a scored input: two
objects of different types are different kinds of thing, and no
amount of name or classification similarity should be able to
compensate for that. This was already true and is not reconsidered
here.

**`relationships` is named and deliberately left out**, not forgotten.
Comparing two objects' `relationships` lists for identity purposes is a
graph-comparison problem — it requires the *targets* of those
relationships to already have resolved identities, which is circular
with identity resolution itself
([OCOM-Object-Intelligence-v0.1.md §8](OCOM-Object-Intelligence-v0.1.md#8-interaction-with-identity-resolver)
already named this exact circularity for a different component).
Nothing in this codebase populates `relationships` yet either. Adding
it as a scored signal now would be designing against data that doesn't
exist — the same mistake this ADR exists to avoid making with
`classification`'s weight.

## 2. Classification Requirement

Three options, as posed:

- **A — Mandatory.** No `classification` overlap, no `MATCH`, ever.
- **B — Reinforcing signal.** `classification` always contributes to
  the score, present or not, the same way it does today.
- **C — Fallback.** `classification` matters only when
  `metadata["identity"]` similarity alone is not already decisive.

**Decision: C.**

The deciding argument is concrete, not stylistic: **Option A is what
the current, un-examined arithmetic already implements, and it makes
`LLMDocumentNormalizer`'s output structurally incapable of ever
producing a real `MATCH`**, because that Normalizer never populates
`classification`. Two documents with an identical, LLM-extracted
`concept` and strong `Evidence` on both sides — the exact case this
whole pipeline was built to eventually resolve — would be capped at
`UNCERTAIN` forever under Option A. That cannot be the intended
semantics; it is an accident of two numbers chosen for a different
test.

Option B does not fix this either, not as stated: a flat, always-applied
weight for `classification` still penalizes its absence unless the
weighting formula is specifically taught to treat "missing" as
"neutral" rather than "zero" — which is itself a fallback rule wearing
Option B's name.

Option C states the actual intended behavior directly: `classification`
is consulted **only when `metadata["identity"]` similarity is
ambiguous** — not decisively high, not decisively low. Concretely,
three bands, by name only (numeric boundaries are explicitly deferred
to §5 / the "Next Step" section, not decided here):

- **Identity similarity is strong** → `MATCH` is reachable on identity
  alone (plus the existing `Evidence` gate, §3) — `classification`
  is not required to confirm an already-strong match.
- **Identity similarity is ambiguous** → `classification` is the
  deciding factor. Overlapping classification pushes toward `MATCH`
  or a higher-confidence `UNCERTAIN`; absent or non-overlapping
  classification keeps the result at `UNCERTAIN`.
- **Identity similarity is weak** → `NEW`, regardless of
  `classification`. A shared classification tag between two clearly
  differently-named objects must never manufacture a `MATCH` on its
  own — the same principle
  [test_false_match_protection_attributes_cannot_manufacture_a_match](../../tests/test_identity_namespace_migration.py)
  already established for `attributes`, generalized to `classification`.

## 3. Evidence Role

**Decision: both roles exist, but only one is implemented in v0.1.**

- **Existence gate (current, unchanged):** `Evidence` must be present
  on both sides for `MATCH` to be reachable at all — binary, already
  implemented, already correct per Memory/Confidence.md.docx
  ("confidence shall not exist without supporting evidence").
- **Confidence gradation (not implemented, named as directionally
  correct):** Memory/Confidence.md.docx's own definition of what
  influences confidence explicitly includes *"number of supporting
  sources"* — meaning an object corroborated by evidence from multiple,
  independent sources should plausibly justify a higher confidence
  label than one with a single evidence entry, even at the same
  `MATCH` outcome. The current resolver does not count or weigh
  evidence beyond presence/absence.

This second role is **not enabled by this ADR.** Deciding exactly how
evidence count or source diversity should move a confidence label is
itself a coefficient decision — the precise thing this document exists
to avoid doing without grounding. It is named here so it is not
rediscovered from scratch later, and left for whichever future work
picks up numeric calibration (§6).

## 4. Unknown Classification

The task's own example — an object with only
`metadata["identity"]["name"] = "Affiliate Manager"`, no
`classification` at all — does not have one universal answer. Per the
§2 decision, the answer depends on what it is being compared against:

- **Compared against an object with a near-identical `identity` name
  and `Evidence` present on both sides:** `MATCH` remains reachable.
  Identity similarity alone is in the "strong" band; missing
  `classification` does not block it. This is precisely the case that
  ruled out Option A in §2.
- **Compared against a similar-but-different name** (e.g. "Partner
  Manager") **with no `classification` on either side:** `UNCERTAIN`.
  This is the "ambiguous" band from §2, and `classification` — the
  signal that would normally resolve it, per
  [MILESTONE-003](MILESTONE-003.md) — is unavailable. The honest
  answer under missing information is "not confident," not a guess in
  either direction. This is the same asymmetry
  [OCOM-Identity-Resolution-v0.1.md §5](OCOM-Identity-Resolution-v0.1.md#5-failure-modes)
  already committed to: prefer an unresolved `UNCERTAIN` (or a
  duplicate `NEW`) over a guessed `MATCH`.
- **Compared against a clearly different name** (e.g. "Payment
  Manager"): `NEW`, regardless of `classification`'s presence. The
  "weak" band is decided by identity dissimilarity alone; missing
  classification changes nothing here because classification was never
  going to be consulted for this band either way.

**Missing `classification` is not, by itself, a reason to downgrade a
decision that identity similarity alone already made confidently.** It
only matters in the band where nothing else has already decided the
outcome.

## 5. Non-Goals

- LLM-based resolution — not justified by this document; nothing here
  changes that standing finding.
- Embeddings, vector search
- Any change to `core/`, `interfaces/`, `storage/`, `agent/`
- **Changing `MATCH_THRESHOLD`, `UNCERTAIN_THRESHOLD`,
  `METADATA_WEIGHT`, or `CLASSIFICATION_WEIGHT`** — this ADR decides
  what these numbers are supposed to mean (§2's three bands); it does
  not decide what the numbers should be. That is explicitly
  `IdentityResolver v0.2` work, informed by this document, not
  performed by it.
- Adding `relationships` as a scored signal (§1) — named, not
  implemented, pending the same identity-resolution-of-targets
  circularity already on record in
  [OCOM-Object-Intelligence-v0.1.md §8](OCOM-Object-Intelligence-v0.1.md#8-interaction-with-identity-resolver).
- Evidence-count-based confidence gradation (§3) — named as
  directionally correct, not specified or implemented.

## 6. Next Step

The task poses this as a choice between two follow-ups. **Recommendation:
Object Intelligence Classification Engine before `IdentityResolver v0.2`.**

The §2 signal model (Option C) is only useful in practice if
`classification` data actually exists to fall back on. Today, it
mostly doesn't: `LLMDocumentNormalizer` — the Normalizer most likely to
produce ambiguous-band comparisons in the first place, since it is the
one doing semantic extraction — never populates `classification`.
Recalibrating `IdentityResolver`'s thresholds and weights now would
mean tuning the "ambiguous band" logic against a signal that is absent
for most real objects in this system today. That is optimizing the
wrong bottleneck first.

Building the Classification Engine
([OCOM-Object-Intelligence-v0.1.md §5.1](OCOM-Object-Intelligence-v0.1.md#51-classification-engine))
gives real `classification` data to tune `IdentityResolver v0.2`
against — the same discipline this ADR itself applied: **don't
calibrate a fallback signal's weight before there is real fallback
data to calibrate it against.** `IdentityResolver v0.2` remains the
correct next step after that, not instead of it.
