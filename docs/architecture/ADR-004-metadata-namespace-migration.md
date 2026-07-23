# ADR-004: Metadata Namespace Migration v0.1

**Status:** Accepted
**Date:** 2026-07-23
**Applies to:** how `OCOMObject.metadata` moves from its current flat shape to the three namespaces decided in [ADR-003](ADR-003-metadata-semantic-boundary.md) (`identity` / `attributes` / `technical`)
**Not touched by this ADR:** `core/object.py`, `core/evidence.py`, `interfaces/`, `storage/`, `agent/`, `identity/`, and both existing Normalizers. This document decides *how* the migration should happen and *who* may write what; it performs none of it.

## Context

[ADR-003](ADR-003-metadata-semantic-boundary.md) decided the target
shape:

```
# Current (both existing Normalizers write this today)
metadata:
{
  "filename": "...",
  "extension": "...",
  "content_length": 123,
  "concept": "OCOM Object"
}

# Target
metadata:
{
  "identity":   { "concept": "OCOM Object" },
  "technical":  { "filename": "...", "extension": "...", "content_length": 123 }
}
```

but explicitly left *how to get there safely* as follow-up work
(ADR-003 Consequences, items 1–4). This document is that follow-up. It
does not implement the migration — it decides the strategy, the
namespace ownership rules, and the content rules for `identity`, so
that when the migration is implemented it has a single, already-agreed
shape to move toward rather than being designed ad hoc, file by file.

## 1. Migration Strategy

**Option A — Breaking migration.** Replace flat keys with namespaced
ones everywhere at once: both Normalizers, `identity/resolver.py`,
`agent/registry.py`, and every affected test, in one coordinated
change.

**Option B — Backward compatible.** Consumers accept both shapes for a
transition period; producers migrate one at a time; nothing breaks
mid-migration.

**Option C — Versioned metadata schema.** Every object carries an
explicit `metadata["metadata_schema_version"]` (or similar) field, and
consumers branch on its value.

**Decision: Option B**, with one refinement — **no separate version
field.** The presence or absence of the namespace keys themselves
(`"identity"`, `"attributes"`, `"technical"` present at the top level
of `metadata`) *is* the version signal. A consumer checks
`"identity" in obj.metadata` the same way it would check a
`metadata_schema_version` field, without introducing a new key that
would itself need governance (who bumps it, what values are valid,
what happens between versions 2 and 3). This is the shape already
self-describing, not a shape that additionally declares itself.

**Why not A:** every prior phase of this project — Reader, Agent,
Identity Resolution, Object Intelligence — was built and verified in
small, independently-testable steps, never as a single coordinated
change across every consumer at once. A metadata shape change is not
an exception to that discipline; it is exactly the kind of change the
discipline exists for. Option A would require touching two Normalizers,
a resolver, a registry, and an unknown number of tests in lockstep,
with no way to verify one piece before the next.

**Why not C:** schema versioning is the right tool for an *ongoing*
pattern of evolution — and Language/Serialization.md.docx explicitly
recommends carrying version information in serialized models. But
nothing about this project's history yet establishes that `metadata`'s
shape changes repeatedly enough to justify permanent versioning
infrastructure: this is the *first* such change. Building a
version-negotiation mechanism now, for a single one-time transition
whose end state is already fully specified by ADR-003, is exactly the
kind of infrastructure-before-a-proven-need this project has
consistently avoided (most recently in
[OCOM-Identity-Resolution-v0.1.md §3](OCOM-Identity-Resolution-v0.1.md#3-decision-model)'s
deferral of Option D). If `metadata`'s shape changes again after this,
*that* is the point to reconsider Option C — with two real data points
instead of one.

**Sunset condition for the backward-compatible fallback:** once both
existing Normalizers write the namespaced shape and every test fixture
in the repository has been updated to match (ADR-003 Consequences,
items 2 and 4), any code path that still reads the flat legacy shape
becomes dead code and should be deleted in its own follow-up change —
not left indefinitely "for compatibility" with data that no longer
exists anywhere in this project.

## 2. Namespace Ownership

Who may **write** to each namespace. Read access was already decided
per-consumer in [ADR-003](ADR-003-metadata-semantic-boundary.md) and
is not repeated here except where relevant.

| Layer | `identity` | `attributes` | `technical` |
|---|---|---|---|
| **Adapter** | ❌ | ❌ | ❌ — Adapters never produce `OCOMObject` at all ([ADR-001](ADR-001-normalizer-architecture.md)); the question does not apply |
| **Normalizer** | ✅ *candidate only* | ❌ | ✅ |
| **Object Intelligence** | ❌ | ✅ | ❌ |
| **IdentityResolver** | ❌ | ❌ | ❌ — pure decision function, no side effects ([OCOM-Identity-Resolution-v0.1.md §1](OCOM-Identity-Resolution-v0.1.md#1-responsibility)) |
| **Registry / Storage** | ❌ | ❌ | ❌ — persistence and search only, never originates content |
| **Agent** (`AnswerComposer`, etc.) | ❌ | ❌ | ❌ — read-only, no write-back ([OCOM Agent v0.1 Design §8](OCOM-Agent-v0.1-Design.md#8-security-boundaries)) |

Two rules this table implies, stated explicitly because they are easy
to get wrong by extension rather than by direct violation:

- **`identity` has exactly one writer: `Normalizer`, at ingestion
  time.** Object Intelligence's "semantic normalization" responsibility
  ([OCOM-Object-Intelligence-v0.1.md §4](OCOM-Object-Intelligence-v0.1.md#4-responsibilities))
  produces a canonical name — but it writes that finding into
  `attributes` (e.g. `attributes["canonical_name"]`, evidenced and
  confidence-scored like everything else it produces), *not* into
  `identity`. Letting a second layer write `identity` after ingestion
  would reopen exactly the "which field is authoritative" ambiguity
  [ADR-003](ADR-003-metadata-semantic-boundary.md) closed for
  `classification`. Object Intelligence's identity-relevant findings
  are proposals for `IdentityResolver` to weigh, same as anything else
  in `attributes` — not a second, competing candidate identity.
- **"Candidate only" for `Normalizer` writing `identity` is not a
  marker stored anywhere — it is what `IdentityResolver` already does
  with the value.** Per
  [OCOM-Identity-Resolution-v0.1.md §2](OCOM-Identity-Resolution-v0.1.md#2-input--output-contract),
  every object's proposed identity is a candidate until a resolution
  decision says otherwise; nothing needs an extra "is this confirmed"
  flag, because `IdentityResolver` never treats any stored value as
  pre-confirmed in the first place.

## 3. Identity Namespace Rules

The single most important rule here is a direct, evidence-backed
consequence of [MILESTONE-003](MILESTONE-003.md): **`identity` is for
values that name the object, not values that describe it.** A name is
compared for identity; a description is not, and feeding one into the
same comparison a name gets is exactly what produced MILESTONE-003's
false `MATCH`.

**Allowed**, matching the task's own example:

```
identity:
{
  "concept": "OCOM Object",
  "canonical_name": "OCOM Object",
  "aliases": ["OCOM Objects", "Object (OCOM)"]
}
```

Every value is a short label — a name or a list of alternate names.
Nothing here is a sentence.

**Forbidden**, matching the task's own example:

```
identity:
{
  "description": "long text..."
}
```

By the same name-vs-description test, also forbidden: `summary`,
`responsibility`, `notes`, or any key whose value is prose rather than
a label — these belong in `attributes` (Object Intelligence's domain)
or nowhere in `metadata` at all, never in `identity`.

**On evidence and confidence for `identity` values:** unlike
`attributes` (which requires per-field `evidence`/`confidence`/
`timestamp` per
[OCOM-Object-Intelligence-v0.1.md §5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment)),
`identity` values written by a Normalizer are backed by the object's
overall `evidence` list, not individually tagged per field. This is a
deliberate difference in rigor, not an oversight: at Normalizer time
there is exactly one raw record and one resulting `Evidence` entry to
attribute anything to — requiring per-field evidence at that stage
would be inventing bookkeeping a single-source translation step has no
use for. Object Intelligence's later, cross-cutting analysis is where
per-field evidence starts to earn its cost.

**On mechanical enforcement:** this document does not propose
validation code that rejects a `description`-shaped value written into
`identity`. The name-vs-description line is enforced by this
convention and by review, not by a runtime check — the same way this
project has repeatedly preferred a stated, reasoned convention over
speculative validation logic until a real violation demonstrates the
convention alone is not enough. If that happens, it is a small, targeted
follow-up, not a reason to have built the check preemptively here.

## 4. Compatibility Impact

- **`IdentityResolver`** — **not fixed by this ADR, and this document
  says so plainly rather than implying otherwise.** Under Option B, the
  resolver's current code is untouched, which means it still reads
  *all* of `metadata.values()` — including a newly-namespaced object's
  `attributes` and `technical` contents — exactly as before. Namespacing
  `metadata` makes the fix specified in
  [ADR-003 Consequences #1](ADR-003-metadata-semantic-boundary.md#consequences)
  possible and well-defined; it does not apply that fix. Until
  `_metadata_tokens()` is actually changed to read only
  `metadata.get("identity", {})`, MILESTONE-003's contamination risk
  remains live for any object that has been given a populated
  `attributes` namespace. That resolver change is separately scoped,
  future work — not part of this migration design.
- **`Registry`** (`agent/registry.py`) — same situation as
  `IdentityResolver`: unaffected until separately updated. Per
  [ADR-003 Consequences #3](ADR-003-metadata-semantic-boundary.md#consequences),
  `Registry`'s eventual namespace selection may legitimately differ
  from `IdentityResolver`'s (broader, since its purpose is
  discoverability, not identity comparison) — that is its own future
  decision, not fixed by this document.
- **`Agent`** (`EvidenceAggregator`, `AnswerComposer`) — **no impact,
  and none expected.** Neither reads `metadata` for anything; both
  operate on `Evidence`. This migration is invisible to them regardless
  of which strategy was chosen.
- **Existing tests** — under Option B, **zero existing tests are broken
  by this ADR**, because nothing is implemented by it. When the
  migration is eventually carried out, the following are the concrete
  fixtures that will need updating (named here so the future
  implementation task does not have to rediscover them):
  `tests/test_identity_resolver_experiment.py`,
  `tests/test_identity_object_representation_experiment.py`
  (flat `metadata={"name": ...}` / `{"name": ..., "responsibility": ...}`),
  `tests/test_llm_document_normalizer.py`,
  `tests/test_llm_normalizer_same_object_recognition.py`
  (`LLMDocumentNormalizer`'s flat `metadata["concept"]`), and
  `tests/test_filesystem_documentation_normalizer.py`
  (flat `filename`/`extension`/`size_bytes`/`content_length`). None of
  these need to change today; they are the known scope of the
  follow-up, not a task list for this document to execute.

## 5. Non-Goals

- No code — no Normalizer, no `identity/resolver.py`, no
  `agent/registry.py`, no test is modified by this document.
- No migration execution — nothing is actually moved from flat
  `metadata` to namespaced `metadata` here.
- No change to `OCOMObject`, `Evidence`, or any file under
  `interfaces/`.
- No `metadata_schema_version` field, or any other new version-tracking
  mechanism — explicitly rejected in §1, not merely deferred.
- No mechanical validation of the `identity`-namespace content rules
  (§3) — convention only, for now.
- No re-litigation of which namespaces exist or what `IdentityResolver`
  is allowed to read — both already decided in
  [ADR-003](ADR-003-metadata-semantic-boundary.md); this document only
  adds *how to get there* and *who may write what*.
