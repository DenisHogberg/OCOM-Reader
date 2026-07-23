# ADR-003: Metadata Boundary and Semantic Field Access

**Status:** Accepted
**Date:** 2026-07-23
**Applies to:** the internal shape of `OCOMObject.metadata` (no schema change), and how `identity/resolver.py` is expected to read it once this ADR is implemented
**Builds on:** [OCOM Object Intelligence Layer v0.1](OCOM-Object-Intelligence-v0.1.md) §8/§11, [MILESTONE-003](MILESTONE-003.md), [OCOM Identity Resolution v0.1](OCOM-Identity-Resolution-v0.1.md)
**Not touched by this ADR:** `core/object.py` (`OCOMObject`'s schema is unchanged — `metadata` remains `dict[str, Any]`), `core/evidence.py`, `interfaces/`, `storage/`, `agent/`, `identity/`. This document decides a convention; it implements nothing.

## Context

[OCOM Object Intelligence Layer v0.1 §8](OCOM-Object-Intelligence-v0.1.md#8-interaction-with-identity-resolver)
named a concrete, unresolved conflict: `OCOMObject.metadata` is used for
two purposes that pull against each other.

1. **Storing structured object data.** Object Intelligence's design
   already committed to this shape for derived attributes:
   ```
   metadata["attributes"] = {
     "responsibility": {"value": ..., "evidence": [...], "confidence": ..., "timestamp": ...},
     "domain": {...},
   }
   ```
2. **Search and similarity scoring in `IdentityResolver`.** The
   resolver's current, unmodified implementation does:
   ```
   stringify(metadata)  →  tokens  →  similarity
   ```
   — it stringifies and tokenizes *every* value in `metadata`, with no
   awareness that some of those values are structured records with
   their own confidence and evidence, not raw comparable text.

[MILESTONE-003](MILESTONE-003.md) already proved this is not a
hypothetical concern: a free-text value in `metadata`, scored the same
way as everything else, produced a false `MATCH` between two distinct
roles. Object Intelligence's structured `attributes` shape makes the
*data* auditable, but does nothing to stop the *resolver* from
stringifying that same structured record and tokenizing it — the
conflict is architectural, not cosmetic.

## Options Considered

### Option A — Resolver gets a whitelist of fields

`IdentityResolver` reads only specific, named keys — e.g.
`metadata["identity_signals"]` and the existing top-level
`classification` field — and ignores everything else (`attributes`,
`evidence`-derived descriptions, etc.).

### Option B — Semantic metadata namespaces

`metadata` gets a small, fixed set of top-level namespaces, each
consumer reading only the namespace(s) relevant to it:

```
metadata:
{
  "identity":   {},   # values that identify what the object is — used for comparison
  "attributes": {},   # structured, evidenced facts (already specified in the Intelligence Layer design)
  "technical":  {},   # filename, size, encoding — descriptive, never compared for identity
}
```

One correction to the task's own example is made here: the task's
Option B example also included a `"classification"` namespace inside
`metadata`. `OCOMObject` already has a dedicated top-level
`classification: list[str]` field
([core/object.py](../../src/ocom_reader/core/object.py)), used by
`IdentityResolver` today. Duplicating it inside `metadata` would create
two competing homes for the same concept, which
Core/Modeling-Rules.md.docx Rule 8 ("Models must avoid duplication...
Duplicate models should not exist") rules out directly. This ADR's
namespace set is `identity` / `attributes` / `technical` — three, not
four — with `classification` left exactly where it already is.

### Option C — Move Intelligence data to a separate record

`OCOMObject` stays exactly as it is; everything Object Intelligence
derives is persisted as a separate `Object Intelligence Record`,
linked to the original object by identity (e.g. its own identity as
`f"intelligence:{original.identity}"`, referencing the original via a
`relationship_type`, retrievable through the existing, unmodified
`Storage` interface with no new persistence mechanism).

## Evaluation

| Criterion | Option A (whitelist) | Option B (namespaces) | Option C (separate record) |
|---|---|---|---|
| Preserves "one object" principle | Yes | Yes | **No** — see below |
| Evidence compatibility | Unaffected | Unaffected | Evidence would need to be split across two records, or `EvidenceAggregator`-equivalent logic duplicated to merge them |
| Impact on Core schema | None | None | None *in schema*, but requires a new identity-naming/relationship convention layered on top |
| Migration complexity | Lowest — purely additive, one new key | Moderate — reshapes `metadata` output in both existing Normalizers | Highest — new lookup convention, every consumer of "intelligence" must learn to fetch and join a second record |
| Suitability for future Agent consumers | Poor — a single-purpose key only serves `IdentityResolver`; each future consumer (`Registry`, a future `AnswerComposer` nuance) would need its own separate whitelist, repeating the same problem | Good — any consumer declares which namespace(s) it reads, using one shared convention, not a new ad hoc list per consumer | Poor — every consumer of enriched data must be updated to fetch and merge a second record just to see it |

**Option C is rejected outright, not merely ranked lowest.** It
directly contradicts a decision [already made and accepted](OCOM-Object-Intelligence-v0.1.md#10-non-goals)
in the Object Intelligence Layer design: *"A new persisted 'Object
Intelligence View' separate from the `OCOMObject` itself — ruled out
explicitly... not merely unaddressed."* and the design's core
principle, *"Object Intelligence does not create a new object."*
Adopting Option C now would mean reopening and reversing that decision
in the same breath as citing it, which this ADR does not do. If a
future case genuinely requires it, that reversal needs its own ADR
that engages with why the original reasoning no longer holds — not a
side effect of solving the metadata boundary problem.

**Option A is rejected as insufficient, not wrong.** It solves
`IdentityResolver`'s specific case correctly, but it is a single-purpose
patch: the whitelist key name and its contents are meaningful only to
this one consumer. The moment a second consumer needs a different
slice of `metadata` — and [OCOM Object Intelligence Layer v0.1 §9](OCOM-Object-Intelligence-v0.1.md#9-interaction-with-agent)
already names a plausible one (`AnswerComposer` eventually
distinguishing observed from derived evidence) — Option A offers no
reusable answer, only the option to invent another ad hoc key. That is
the same duplication Rule 8 already rules out for the
`metadata`/`classification` overlap above, just deferred rather than
avoided.

## Decision

**Option B — semantic metadata namespaces — is adopted.** `metadata`
is partitioned into three namespaces: `identity`, `attributes`,
`technical`. This is treated as a formalization of a decision Object
Intelligence's design had already begun to make on its own
(`metadata["attributes"]`'s structured shape,
[§5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment)),
extended to a complete, closed set rather than left as one namespace
next to an undifferentiated rest of `metadata`.

Namespace responsibilities:

- **`metadata["identity"]`** — values that identify what the object
  is and are appropriate for identity comparison (e.g. a canonical
  concept name). This is the only `metadata` namespace `IdentityResolver`
  is expected to read.
- **`metadata["attributes"]`** — structured, evidenced facts, exactly
  as specified in [Object Intelligence Layer §5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment)
  (`value` / `evidence` / `confidence` / `timestamp` per field). Never
  read by `IdentityResolver`.
- **`metadata["technical"]`** — descriptive, administrative facts
  (filename, extension, size, encoding) that describe the object but
  say nothing about its identity. Never read by `IdentityResolver`.

### IdentityResolver's access, decided explicitly

The task asks this directly: should `IdentityResolver` see all of
`metadata`, only identity-related fields, or a separate projection
layer? **Only identity-related fields** — concretely,
`OCOMObject.object_type` and `OCOMObject.classification` (both
unchanged, top-level, already read today) plus `metadata["identity"]`
only. Not all of `metadata`. Not a separate projection layer either:
once namespacing exists inside `metadata` itself, a projection
computed on top of it would be solving the same problem a second time,
at the cost of another abstraction between `OCOMObject` and the
resolver that nothing has justified yet — the same "don't add a layer
before a proven need" standard already applied to Object Intelligence's
own architectural questions.

## Consequences

This ADR is a decision, not an implementation — the following are the
concrete changes it implies, none of them made here:

1. **`identity/resolver.py`'s `_metadata_tokens()` must change** from
   iterating `obj.metadata.values()` (all of them) to reading
   `obj.metadata.get("identity", {})` only. This is the actual fix for
   the contamination gap named in
   [OCOM Object Intelligence Layer v0.1 §8](OCOM-Object-Intelligence-v0.1.md#8-interaction-with-identity-resolver) —
   this ADR only authorizes and specifies it; a future task must make
   the change and re-run
   [MILESTONE-003](MILESTONE-003.md)'s experiments to confirm all four
   original outcomes (`MATCH`, `NEW`, `UNCERTAIN`, evidence-gated
   `UNCERTAIN`) still hold under the new access rule.
2. **Both existing Normalizers' `metadata` output need to move to this
   shape.** `FilesystemDocumentationNormalizer` and
   `LLMDocumentNormalizer` currently write flat keys
   (`filename`/`extension`/`size_bytes`/`content_length`,
   `concept`/`confidence`). These need to be sorted into namespaces —
   `concept` into `identity`, `confidence` and the file-derived facts
   into `technical` — a small, bounded change (two files) since no
   Object Intelligence code has been built yet to migrate.
3. **`agent/registry.py`'s `find_candidates()` should be revisited**,
   but not necessarily to the same `identity`-only rule.
   [ADR-002](ADR-002-agent-vertical-slice-boundaries.md) already named
   its keyword search as a placeholder; `Registry`'s purpose
   (discoverability) is broader than `IdentityResolver`'s (identity
   comparison), so it may legitimately want to search `identity` +
   `attributes` + `technical` while `IdentityResolver` reads only
   `identity`. This is exactly the case Option A could not have served
   without a second, separately-invented whitelist — one shared
   namespace convention, read differently by different consumers, is
   what makes this a one-time decision rather than a recurring one.
4. **Existing test fixtures that construct `OCOMObject(metadata={"name": ...})`
   with flat keys** (`test_identity_resolver_experiment.py`,
   `test_identity_object_representation_experiment.py`) will need
   updating to place `"name"` (or its equivalent) under
   `metadata["identity"]` once change (1) lands, or those tests will
   silently stop exercising what they currently test.
5. **Object Intelligence Layer's future implementation is unaffected
   in shape** — `metadata["attributes"]` was already specified with
   exactly this namespace name and structure; this ADR confirms it
   rather than changing it.

None of items 1–4 are implemented by this document. They are the
specific, scoped follow-up work this decision creates.
