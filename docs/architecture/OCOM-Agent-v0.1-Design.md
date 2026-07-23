# OCOM Agent v0.1 — Design

**Status:** Draft — design only, nothing in this document has been implemented.
**Date:** 2026-07-23
**Builds on:** [MILESTONE-001](MILESTONE-001.md) (OCOM Reader Architecture Freeze v0.1), [ADR-001](ADR-001-normalizer-architecture.md) (Normalizer architecture)
**Core contracts this design does not touch:** `core/object.py`, `core/evidence.py`, `interfaces/adapter.py`, `interfaces/normalizer.py`, `interfaces/storage.py`. Any change to those requires its own ADR — none is proposed here.

## Section Status (added by [Architecture Consistency Cleanup v0.1](Architecture-Status-v0.1.md))

This document was written before any of it was implemented. Several
validation-experiment tasks since then built real components that
diverge from what's sketched below — not through any single ADR
reversing this document, but through a series of scoped-down
implementation choices none of which were reflected back here until
now. Per section, not rewritten:

| Section | Status | Why |
|---|---|---|
| §1 Purpose | **Still valid** | The Agent's job description (find, resolve, aggregate, answer, cite) matches what was actually built. |
| §2 Architecture Overview | **Still valid**, except the package sketch | "Agent reads only from `Storage`, never `Adapter`" held. The file layout showing `agent/identity_resolver.py` did not — `IdentityResolver` was built in its own top-level `identity/` package, sibling to `agent/`, not inside it. |
| §3 Components | **Superseded by implementation** | The component table and their listed dependencies (e.g. `EvidenceAggregator` depending on `ObjectRegistry`) do not match what exists — see §4's note. |
| §4 Interfaces | **Superseded by implementation** | None of the concrete signatures shown were built as specified: `IdentityResolver.resolve()` takes two `OCOMObject`s (`identity/resolver.py`), not one, and `IdentityDecision` has fields `result`/`confidence`/`reasoning`/`matched_object_id`, not `outcome`/`canonical_identity`/`matched_identity`/`reason`; `EvidenceAggregator.aggregate()` takes `objects: list[OCOMObject]` directly, not a `canonical_identity` string via an injected `Registry`; `AnswerComposer.compose()` takes no `query` parameter and returns a flat `Answer(text, sources, grounded)`, not `AgentAnswer(query, statements, unresolved)`; `QueryEngine` and the `OCOMAgent` facade were never built at all — `agent/registry.py`'s `find_candidates(query)` absorbed search directly. This section is kept as a record of original intent, not a description of the code. |
| §5 Data Flow | **Still valid at the conceptual level, superseded in call shape** | The ingestion-time and query-time sequencing (Normalizer → resolve → register/merge; Query → search → resolve → aggregate → answer) reflects what was built. The specific method calls shown (§4) do not. |
| §6 Identity Resolution Strategy | **Superseded by [ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-005](ADR-005-identity-resolution-signal-model.md), and [OCOM-Identity-Resolution-v0.1.md](OCOM-Identity-Resolution-v0.1.md)** | "Identity Resolution lives in the Agent layer, not the Normalizer" still holds. The specific matching mechanism described here (exact-match on normalized `metadata["concept"]`, no other signal) was superseded first by Option B rule-based similarity (`OCOM-Identity-Resolution-v0.1.md` §3), then by the `identity`/`attributes`/`technical` namespace split (ADR-003) and the classification-as-fallback signal model (ADR-005). |
| §7 Evidence Handling | **Still valid** | Merge-at-write, append-only — confirmed by [ADR-002](ADR-002-agent-vertical-slice-boundaries.md) and reused as the pattern for enrichment history in [OCOM-Enrichment-Provenance-v0.1.md](OCOM-Enrichment-Provenance-v0.1.md). |
| §8 Security Boundaries | **Still valid** | Nothing built since has contradicted any boundary listed here. |
| §9 Explicit Non-Goals | **Still valid** | None of these have been built; several are reaffirmed verbatim in later documents. |
| §10 Open Questions | **Mixed** | Q2 (matching heuristic beyond exact match) and Q3 (need a third, ambiguous outcome) are resolved — Option B similarity and the `MATCH`/`NEW`/`UNCERTAIN` three-outcome model, respectively, both realized in `identity/`. Q5 (is an LLM required in `AnswerComposer`) is resolved: no, per ADR-002. Q1, Q4, Q6 remain genuinely open. |

## 1. Purpose

OCOM Reader (Phase 1) proved that raw data from a source can be turned
into a stable `OCOMObject` with attached `Evidence`, behind interfaces
that let the source and the extraction strategy change without
touching the core. It stopped there deliberately: one object in,
one object out, no notion of "have we seen this before."

OCOM Agent v0.1 is the first layer that reads *across* what Reader has
already produced. It does not ingest anything new and does not extract
anything from raw sources — it operates entirely on `OCOMObject`
instances that already exist in `Storage`. Its job is:

1. Find existing `OCOMObject`s relevant to a new candidate or to a
   query.
2. Decide whether a new candidate refers to an object that already
   exists, or is genuinely new.
3. Combine `Evidence` from multiple sources into one view of an
   object.
4. Answer questions using only that `Evidence` — never inventing a
   fact that no `Evidence` supports.
5. Show where every part of an answer came from.

This is the layer where Identity Resolution — deliberately deferred in
[ADR-001](ADR-001-normalizer-architecture.md) and confirmed absent
from `LLMDocumentNormalizer` in [MILESTONE-001](MILESTONE-001.md) — is
meant to live.

## 2. Architecture Overview

The Agent is a new layer downstream of the Reader pipeline, not a
replacement of any part of it:

```
                         READER (Phase 1 — unchanged)
Source → Adapter → Raw Data → Normalizer → OCOMObject (candidate)
                                                  │
                                                  │  candidate crosses
                                                  │  into the Agent layer
                                                  ▼
                         AGENT (Phase 2 — this design)
                    ┌─────────────────────────────────────┐
                    │  Identity Resolution  →  Registry     │
                    │           │                            │
                    │           ▼                            │
                    │        Storage (existing interface)     │
                    └─────────────────────────────────────┘
                                     ▲
                                     │  reads only, never fetches
                                     │  from a live source
                    ┌─────────────────────────────────────┐
                    │  Query → Search → Identity Resolution  │
                    │        → Evidence Aggregation           │
                    │        → Answer Composer                │
                    └─────────────────────────────────────┘
```

Two things follow from this shape:

- **The Agent has exactly one way to reach data: `Storage`.** It never
  calls `Adapter.fetch()` and never talks to a source system directly.
  Everything it knows was already normalized and evidenced by Reader.
- **Identity Resolution is reused, not duplicated, across two call
  sites**: once when a new candidate arrives (ingestion-time — "is
  this new or existing?"), and once when a query is answered
  (query-time — "which stored objects does this question refer to?").
  One component, two callers — see §6.

All new components live in a new package, `agent/`, sitting alongside
`adapters/`, `normalizers/`, `storage/` — not inside any of them:

```
src/ocom_reader/
  core/            unchanged
  interfaces/      unchanged
  adapters/        unchanged
  normalizers/     unchanged
  storage/         unchanged
  agent/           new — everything in this document
    identity_resolver.py
    registry.py
    evidence_aggregator.py
    query.py
    answer_composer.py
```

## 3. Components

| Component | Responsibility | Depends on |
|---|---|---|
| `IdentityResolver` | Decide if a candidate `OCOMObject` is new or matches an existing one | `ObjectRegistry` |
| `ObjectRegistry` | Known-object lookup, candidate search, alias mapping, lifecycle-aware filtering | `Storage` (existing interface) only |
| `EvidenceAggregator` | Combine `Evidence` from every record that resolves to one identity into a single view | `Storage`, `ObjectRegistry` |
| `QueryEngine` (Search) | Turn a free-text query into a set of candidate objects | `Storage` |
| `AnswerComposer` | Turn an aggregated view into an answer where every statement cites its `Evidence` | `EvidenceAggregator` output only — no direct `Storage` access |

None of these are peers of `Adapter`/`Normalizer`/`Storage` in the
Reader sense — they don't get a new abstract interface file under the
existing `interfaces/` package, because they are not something a
future *source* implements. They are Agent-internal collaborators.
Whether they deserve their own `agent/interfaces/` mirror of the
Reader pattern (for testability via fakes, the same way
`LLMDocumentNormalizer` takes an injected `LLMClient`) is noted as an
open question in §10 rather than decided here.

A thin façade ties them together for the two entry points that matter:

```
OCOMAgent
    ingest(candidate: OCOMObject) -> IdentityDecision
    ask(query: str) -> AgentAnswer
```

## 4. Interfaces

These are illustrative signatures for the design being proposed, not
code to be merged — no implementation exists yet.

```python
# --- Identity Resolution ---------------------------------------------

class IdentityDecision(BaseModel):
    outcome: Literal["new", "match"]
    canonical_identity: str          # candidate.identity if "new"
    matched_identity: str | None     # set only if outcome == "match"
    reason: str                      # human-readable, for audit/logging

class IdentityResolver:
    def resolve(self, candidate: OCOMObject) -> IdentityDecision: ...


# --- Object Registry ----------------------------------------------------
# Wraps the existing Storage interface. Adds no new persistence.

class ObjectRegistry:
    def __init__(self, storage: Storage) -> None: ...

    def find_candidates(self, candidate: OCOMObject) -> list[OCOMObject]: ...
    def register(self, obj: OCOMObject) -> None: ...
    def resolve_alias(self, identity: str) -> str | None: ...
    def merge_evidence(self, canonical: OCOMObject, candidate: OCOMObject) -> OCOMObject: ...


# --- Evidence Aggregation ------------------------------------------------

class UnifiedObjectView(BaseModel):
    identity: str
    object_type: str
    metadata: dict[str, Any]
    evidence: list[Evidence]         # union, every entry's provenance intact

class EvidenceAggregator:
    def __init__(self, registry: ObjectRegistry) -> None: ...
    def aggregate(self, canonical_identity: str) -> UnifiedObjectView: ...


# --- Query / Search -------------------------------------------------------

class QueryEngine:
    def __init__(self, storage: Storage) -> None: ...
    def search(self, query: str) -> list[OCOMObject]: ...


# --- Answer Composer --------------------------------------------------------

class Statement(BaseModel):
    text: str
    evidence: list[Evidence]         # never empty
    confidence: str                  # read from metadata, not computed here

class AgentAnswer(BaseModel):
    query: str
    statements: list[Statement]
    unresolved: bool                 # True if no Evidence supports any statement

class AnswerComposer:
    def compose(self, query: str, view: UnifiedObjectView) -> AgentAnswer: ...
```

Note what is deliberately absent: no new field on `OCOMObject` or
`Evidence`, no new abstract base class replacing `Storage`. `Registry`,
`Aggregator`, and `QueryEngine` all take a `Storage` (or another
Agent-layer object) in their constructor — the same dependency
injection pattern already used by `LLMDocumentNormalizer`'s
`LLMClient`, not a new pattern invented for this layer.

## 5. Data Flow

### 5.1 Ingestion-time (a candidate is produced by Reader)

```
Normalizer output (candidate OCOMObject, own proposed identity, 1 Evidence entry)
        ↓
IdentityResolver.resolve(candidate)
        ↓
   ┌────┴─────┐
   │          │
  "new"     "match"
   │          │
   ▼          ▼
Registry.register(candidate)     Registry.merge_evidence(existing, candidate)
   │                                        │
   ▼                                        ▼
Storage.save(candidate)          Storage.save(merged)      ← still just Storage.save()
```

This replaces today's direct `normalizer.normalize(raw)` →
`storage.save(obj)` call in ingestion glue code with one extra step in
the middle. `Storage.save()` itself does not change; it is called with
a different object depending on the decision.

### 5.2 Query-time

```
"What do we know about OCOM Object?"
        ↓
QueryEngine.search(query)  →  list of loosely matching OCOMObjects
        ↓
IdentityResolver            →  collapse loose matches onto canonical identities
   (same component as 5.1)     (handles the case where Search finds several
                                 stored records that are really one object)
        ↓
EvidenceAggregator.aggregate(canonical_identity)  →  UnifiedObjectView
        ↓
AnswerComposer.compose(query, view)  →  AgentAnswer
```

Example output shape, matching the format requested for this design:

```
OCOM Object lifecycle:

Statement:
"Object has active lifecycle state"

Evidence:
object_en.md
confidence:
derived
```

If `EvidenceAggregator` returns a view with no evidence relevant to the
question, `AnswerComposer` returns `unresolved=True` and no statements
— it does not degrade into a best-effort guess.

## 6. Identity Resolution Strategy

**Where it lives:** Not in `Normalizer` — confirmed by
[ADR-001](ADR-001-normalizer-architecture.md) and
[MILESTONE-001](MILESTONE-001.md) as the wrong place, because a
Normalizer sees one raw record at a time and has no view of what
already exists. It lives in the Agent layer, specifically in
`IdentityResolver`, backed by `ObjectRegistry` (which is the only
component with a view across all stored objects).

**Candidate extraction vs. final identity decision — the split:**

- A Normalizer's output identity (e.g. `LLMDocumentNormalizer`'s
  `concept:<slug>`) is a **candidate identity**, never treated as final
  by the Agent layer. It is a good-faith proposal from a single
  document, nothing more.
- `IdentityResolver` is the only component with authority to say "this
  is a new object" or "this is an existing object." That authority is
  exercised by comparing the candidate against `ObjectRegistry`'s known
  objects and returning an `IdentityDecision` — never by mutating
  `candidate.identity` in place (it's a plain value on an immutable
  pydantic model; a decision is applied by the caller, not by editing
  the candidate).
- Concretely for v0.1: matching is **deterministic and metadata-based**
  — compare `candidate.object_type` and a normalized form of
  `candidate.metadata.get("concept")` (already produced by
  `LLMDocumentNormalizer`, unchanged) against the same fields on every
  object `ObjectRegistry.find_candidates()` returns. No embeddings, no
  vector search, no fuzzy string distance in v0.1 — an exact match on
  normalized concept is either good enough to prove the idea, or it
  fails informatively (a false "new" decision), which is itself useful
  signal for what a v0.2 resolver needs to handle. This mirrors how
  Reasoning Consistency Test v0.1 treated a "wrong" result as valid
  information about the current boundary, not a bug to hide.
- `ObjectRegistry.find_candidates()` is a linear scan over
  `Storage.list()` filtered by `object_type`, not a new index or
  database. This is intentionally the same scale trade-off already
  accepted for `LocalJSONStorage` in MILESTONE-001 — acceptable for
  v0.1's data volume, explicitly not scalable, not being fixed here.
- **Aliasing** is stored as data, not schema: a confirmed match appends
  the candidate's identity to the canonical object's
  `metadata["aliases"]` (the existing, already-flexible `metadata`
  dict — no field added to `OCOMObject`). `resolve_alias()` reads that
  same field. This follows the same pattern already used for
  `confidence` in `LLMDocumentNormalizer` — reuse the schema's escape
  hatch rather than widen the schema.
- **Lifecycle awareness**: `find_candidates()` may exclude objects
  whose `lifecycle_state` marks them as no longer eligible for
  matching (e.g. an archived object should not silently absorb new
  evidence) — again reading the existing `lifecycle_state` field,
  nothing new.

## 7. Evidence Handling

**Aggregation strategy chosen for v0.1: merge at write time, append
only.** When `IdentityResolver` returns `"match"`,
`ObjectRegistry.merge_evidence()` returns a copy of the canonical
object with `evidence = existing.evidence + candidate.evidence`, and
that copy is what gets saved. This is not new design — it is exactly
the pattern already validated in
`tests/test_llm_normalizer_same_object_recognition.py`, promoted from
test-only code to a named, reusable component. No `Evidence` entry is
ever edited or removed; matching only ever appends.

The alternative — never merge at write time, instead have
`EvidenceAggregator` compute a `UnifiedObjectView` at read time by
following `metadata["aliases"]` back to every original record — was
considered because it keeps each normalized record immutable forever.
It was not chosen as the v0.1 default because it requires the Registry
to reliably resolve and fetch N records per query instead of one, for
a benefit (perfect per-ingestion immutability) that nothing in v0.1
needs yet. It is kept open in §10 rather than discarded.

**How contradictions are resolved: they are not resolved, they are
surfaced.** If two `Evidence` entries support different values for the
same fact (e.g. one source implies a "draft" lifecycle, another implies
"active"), v0.1 does not pick a winner. `metadata` and `lifecycle_state`
on the canonical object keep whatever the first-registered object had;
newer, conflicting evidence is still appended and still visible to
`AnswerComposer`, which must surface it as multiple statements with
their own evidence rather than silently picking one. Automatic
conflict resolution requires a real confidence model
(Memory/Confidence.md.docx) and is explicitly out of scope — see §9.
This is a deliberate, not accidental, gap.

**How provenance is preserved:** every `Evidence` entry keeps its own
`source`, `reference`, `captured_at`, and `excerpt` regardless of how
many other entries it is stored alongside. Nothing in this design
computes a new, unattributed fact — `AnswerComposer`'s Statement always
carries the `Evidence` list it was built from (§4, §5.2), so "why do
you believe this" is answerable for every sentence the Agent produces,
not just for the object as a whole.

## 8. Security Boundaries

- **The Agent never touches a source system.** It has no dependency on
  any `Adapter` and cannot fetch, authenticate against, or write to
  GitHub, a CRM, a payment system, or anything else outside `Storage`.
  This bounds the blast radius of anything going wrong in this layer
  to the local `Storage` — nothing external can be affected.
- **Writes are limited to `Storage.save()`.** `IdentityResolver` and
  `ObjectRegistry` never call `Storage.delete()`. v0.1 has no
  autonomous deletion or garbage collection of objects — removing an
  object is a human/governance action, not something this layer does
  on its own.
- **No write-back to source systems, ever, in this design.** Matches
  the explicit non-goal in §9; called out here too because it is a
  security boundary, not just a scope decision — an Agent that could
  write back into a CRM or GitHub on its own inference is a materially
  different (and much riskier) system than the one being designed.
- **Evidence excerpts are data, not instructions, to any LLM used by
  `AnswerComposer`.** Source documents (and, eventually, GitHub issues,
  CRM notes, etc.) are external, potentially untrusted content. If
  `AnswerComposer` uses an LLM to phrase an answer (see §10 — not
  decided as mandatory for v0.1), the prompt must treat every
  `Evidence.excerpt` strictly as content to cite, never as an
  instruction to follow — the same instruction/data boundary this
  design itself is being held to.
- **`IdentityDecision.reason` exists for auditability, not convenience.**
  Every merge is attributable to a specific decision with a recorded
  reason, matching Registry's "Registry Integrity" and "Auditability"
  requirements (Meta/Registry.md.docx) — an unexplained silent merge
  would violate that even if the merge itself were correct.

## 9. Explicit Non-Goals

Not being built in v0.1, on purpose:

- Knowledge Graph database
- Vector database / embedding-based similarity search
- Multi-agent system or any agent-to-agent coordination
- Complex ontology or general-purpose reasoning engine
- Write-back automation into source systems
- Autonomous modification of source systems
- Any new persistent storage technology beyond the existing `Storage`
  interface
- Automatic resolution of conflicting evidence (confidence-weighted or
  otherwise) — evidence is surfaced, not adjudicated
- Any change to `OCOMObject`, `Evidence`, or any file under
  `interfaces/`
- Deletion, archival automation, or retention policy enforcement
- Authentication/authorization — v0.1 is a local, single-tenant design

## 10. Open Questions

Things this document deliberately leaves unresolved, because they need
either a second real data point or actual usage to answer honestly
rather than a guess dressed up as a decision:

1. **Write-time merge vs. read-time aggregation for Evidence** (§7) —
   v0.1 picks write-time merge because it's already validated; is
   read-time aggregation (fully immutable per-source records) worth
   its extra Registry complexity once there's a second real source?
2. **Matching heuristic beyond exact concept match** — what does
   `IdentityResolver` do when two candidates are clearly the same
   object to a human but produce different `metadata["concept"]`
   strings (e.g. "OCOM Object" vs. "OCOM Objects")? Needs real
   multi-source data, not another synthetic bilingual test, to answer
   well.
3. **Ambiguous matches** — `IdentityDecision` only models `"new"` and
   `"match"`. Real data will eventually produce genuine ambiguity
   (candidate plausibly matches two different existing objects). Does
   v0.1 need a third outcome (e.g. `"ambiguous"`, deferred to a human
   review queue), or is that premature until it actually happens?
4. **Does the Agent layer need its own `interfaces/` package**,
   mirroring Reader's `Adapter`/`Normalizer`/`Storage` pattern, so
   `IdentityResolver`/`Registry`/`EvidenceAggregator` are swappable the
   same way? Or is that premature abstraction for a layer with exactly
   one implementation of each so far?
5. **Is an LLM required in `AnswerComposer`, or does a template-based
   composer (statements + evidence, no natural-language phrasing)
   satisfy v0.1's goal on its own?** A template-only composer is
   simpler, has no LLM-injection surface (§8), and may be sufficient to
   prove the "never answer without evidence" contract before adding
   natural-language phrasing on top.
6. **What does `ObjectRegistry.find_candidates()` do at a scale where a
   full `Storage.list()` scan is no longer acceptable?** Known and
   accepted as a v0.1 limitation (§6); not answered here because
   nothing in this project has hit that scale yet.
