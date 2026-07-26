# ADR-007: Memory Before Knowledge

**Status:** Accepted
**Date:** 2026-07-26
**Applies to:** the boundary between raw ingestion (`Adapter`, today's `RawDocument`) and interpretation (`Normalizer`, `OCOMObject`) — introduces one new persisted stage between them.
**Builds on:** [OCOM Knowledge Model v0.1](OCOM-Knowledge-Model-v0.1.md) — "Knowledge" in this ADR *is* the Knowledge Model that document defines (Concept, Knowledge Fragment, Role Binding, Source); this ADR does not redefine it, only fixes what it is built from. [MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md) — the Reasoning Pipeline and Interaction Layer are unaffected by and out of scope for this ADR. [ADR-001](ADR-001-normalizer-architecture.md) — Adapter/Normalizer/Storage separation, which this ADR extends with one new persisted stage rather than replaces.
**Not touched by this ADR:** the Reasoning Pipeline, Interaction Layer, Intent/Audience Analysis (all remain exactly as specified in `MILESTONE-020-DESIGN.md`); the Knowledge Model's own primitives (unchanged, as specified in `OCOM-Knowledge-Model-v0.1.md`); World Model, mentioned here only to name what sits downstream of Knowledge — its own construction is not designed in this document.

## Context

Corporate information arrives from a growing set of sources — documentation today, email, meeting transcripts, and spreadsheets next, Slack, Jira, CRM, GitHub, ERP, BI eventually. If a source is transformed directly into an interpreted form, only the current interpretation survives. When extraction quality improves — this has already happened once in this codebase, a deterministic `Normalizer` replaced by an LLM-based one — there is no way to re-interpret what was already ingested without re-fetching it from the source. For several source types this is not merely expensive, it is impossible: deleted emails, edited messages, superseded documents. As the number of sources grows, so does the amount of history this failure mode can silently destroy.

## 1. Decision

**Knowledge is always derived from Memory.**

Memory exists independently of any interpretation. Knowledge is always a derivative of Memory, never a substitute for it, and never itself a source of new facts about what was originally observed. Everything downstream of Knowledge — up to and including World Model — inherits this same direction: derived, never authoritative over what it was derived from.

"Memory Before Knowledge" names the ordering this produces in the pipeline; the dependency itself — Knowledge derived from Memory, not the reverse — is the actual invariant this ADR fixes.

## 2. Scope

This ADR defines only:

```
Source → Adapter → Memory → Knowledge Extraction → Knowledge
```

It stops at Knowledge. World Model, Reasoning, Intent/Audience Analysis, and the Interaction Layer are not designed, redefined, or extended here — they remain exactly as specified in `MILESTONE-020-DESIGN.md` and whatever future document defines World Model construction. This ADR fixes where Knowledge's inputs come from; it does not describe what happens to Knowledge afterward.

"Knowledge Extraction" is not a new component. It is what `Normalizer.normalize()` already does — interpreting a raw record into structured form — now reading from a persisted Memory Entry instead of a transient `RawDocument`. Whatever combination of existing and future components performs that interpretation (today's `Normalizer`, the Fragment/Role Binding construction already specified in the Knowledge Model) is out of scope for this ADR to enumerate; only the fact that it reads from Memory, and can be re-run against Memory without touching the source, is fixed here.

## 3. Memory Entry

Memory Entry is `RawDocument`, promoted from transient to persisted. Not a new concept — an existing one given a stable identity and a store.

Minimal composition:

- `id` — content hash, not derived from source location
- `source` — which adapter/system produced this record
- `source identifier` — the source-specific reference (message id, file path, sheet and row, etc.)
- `author` / `participants`
- `timestamp`
- `raw content`
- `metadata` — source-specific technical metadata
- `evidence`

Memory Entry is immutable. Once created, it is never edited — only superseded by a new Memory Entry if the same underlying observation changes at the source (e.g., an edited document produces a new content hash, not a mutation of the old entry).

## 4. Invariants

- Memory never depends on Knowledge, Knowledge Extraction, or anything downstream of them.
- Knowledge is always derived from Memory, never the reverse, and never from the original source directly.
- Knowledge can be fully recomputed from Memory at any time, without re-fetching from any source.
- Memory Entry is immutable once created.
- Improving Knowledge Extraction never requires re-ingestion — only re-derivation from already-persisted Memory.

## 5. Consequences

**Advantages:** the full ingested history becomes re-interpretable, not just what was ingested going forward; independence from changes to LLM providers or extraction logic; one storage model for every future source, regardless of how different their interpretation needs are; scaling from a handful of sources to dozens without an architecture change — only new Adapters, the same Memory stage every time.

**Disadvantages, named rather than deferred silently:** storage volume grows with every source added, not just with interpreted output; a retention policy is needed and is not defined by this ADR; sources like email and meeting transcripts carry PII and sensitive content at the raw-observation stage, before any filtering interpretation would normally apply — access control and retention for the Memory store need their own decision, connecting to the Retention concept already named in the canonical OCOM Specification's Memory track, not invented fresh here.

## 6. Relationship to the Capability Roadmap

Architecture and capability are two different models and are not to be merged:

```
Architecture (this ADR + Knowledge Model + future World Model design)
Memory → Knowledge → World Model

Capabilities (cognitive, not architectural)
Reader → Expert → Observer → Analyst → Advisor
```

Memory, Knowledge, and World Model are architectural layers — what is stored and how it derives from what came before. Reader, Expert, Observer, Analyst, and Advisor are not layers and do not correspond one-to-one with them — they are levels of cognitive capability describing what the system can *do* with World Model once it exists, developing along a separate axis from the architecture itself. This ADR governs the first two architectural layers only; it makes no claim about capability sequencing, which is governed separately.
