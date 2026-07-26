# OCOM Architecture Vision v1.0

**Date:** 2026-07-26
**What this is:** an entry point, not a specification, not an ADR, not a roadmap. Every claim below is sourced from an existing document; this page exists so a new reader can orient in 10-15 minutes before going to those documents for detail. If anything here ever conflicts with an ADR, a MILESTONE document, or the canonical OCOM Specification, those win — this page is a map, not the territory.

## 1. Purpose

OCOM is an object-centric operational model: every managed concept in an organization — an Entity, a Domain, a Workflow, an Event, an Organization, a Policy — is a specialization of one universal abstraction, `Object` (canonical OCOM Specification, `Meta/Object.md`). The problem this answers: an organization's operational knowledge is scattered across documentation, communication, and systems that don't share a common model, so nothing can reason across them consistently.

OCOM Reader is the first working implementation built on top of that model. It started as a reference Adapter proving the model is source-agnostic, and has grown into the first component of what this repository's architecture treats as an Operational Memory Platform — a system that reads an organization's information, remembers it, and is meant to eventually reason over it. See [`README.md`](../../README.md) and [ADR-007](ADR-007-memory-before-knowledge.md) for how that positioning was reached.

## 2. Design Philosophy

- **Object-Centric Architecture** — everything managed is a specialization of `Object`. OCOM Specification `Meta/Object.md`; implemented as `core/object.py`.
- **Memory Before Knowledge** — raw observation is persisted before it is interpreted, and interpretation is always re-derivable from it. [ADR-007](ADR-007-memory-before-knowledge.md).
- **Evidence First** — no claim without a traceable origin. Stated independently and consistently across the codebase; see the "Evidence-first reasoning" entry in [Architecture-Status-v0.1.md](Architecture-Status-v0.1.md).
- **Immutable Operational Memory** — a Memory Entry, once created, is never edited. [ADR-007 §3](ADR-007-memory-before-knowledge.md#3-memory-entry).
- **Derived Knowledge** — Knowledge is always computed from Memory, never a second source of truth. [ADR-007 §1](ADR-007-memory-before-knowledge.md#1-decision), [OCOM Knowledge Model v0.1](OCOM-Knowledge-Model-v0.1.md).
- **Explicit Relationships** — connections between things carry meaning and are never implicit. OCOM Specification `Meta/Relationship.md`; implemented as `core/object.py`'s `Relationship`, reused directly by the Knowledge Model rather than reinvented.
- **Explainable Reasoning** — an answer is expected to show what it's grounded in, not just state a conclusion. [MILESTONE-009-010](MILESTONE-009-010.md) (`ComposedAnswer`), extended by [MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md).

## 3. High-Level Architecture

```
External Sources
      ↓
   Memory
      ↓
  Knowledge
      ↓
 World Model
      ↓
  Reasoning
      ↓
 Interaction
```

Each arrow is a real architectural boundary, not an implementation detail — no layer is allowed to see past the one directly below it. Memory and Knowledge are defined by [ADR-007](ADR-007-memory-before-knowledge.md) and the [Knowledge Model](OCOM-Knowledge-Model-v0.1.md). World Model is named but not yet designed — the Knowledge Model document explicitly scopes it out. Reasoning and Interaction are specified in more granular form (Intent Analysis, Audience Analysis, Knowledge Selection, Expert Reasoning, Answer Composition, Interaction Layer) by [MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md) — this diagram collapses that detail on purpose; go there for the actual stage names.

## 4. Architectural Layers

- **Memory** — what was observed. Origin, author, timestamp, raw content, evidence. Nothing interpreted yet.
- **Knowledge** — what a piece of Memory means: Concepts, Fragments, and the Role Bindings connecting them. Fully recomputable from Memory.
- **World Model** — the current, standing understanding built from Knowledge. Not yet designed; see [OCOM-Knowledge-Model-v0.1.md §7](OCOM-Knowledge-Model-v0.1.md#7-what-becomes-possible-on-top-not-designed-here).
- **Reasoning** — what the system does with World Model to answer a specific question, for a specific intent and audience. [MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md).
- **Interaction** — how an answer reaches a person. Optional and additive by construction; see [MILESTONE-019](MILESTONE-019.md).

## 5. Architecture vs Capabilities

These are two different, non-corresponding models — conflating them was an actual mistake caught and corrected while designing ADR-007, worth stating plainly rather than silently avoiding:

```
Architecture                    Capabilities
Memory                          Reader
  ↓                               ↓
Knowledge                       Expert
  ↓                               ↓
World Model                     Observer
                                   ↓
                                 Analyst
                                   ↓
                                 Advisor
```

Architecture is what is stored and how it derives from what came before. Capabilities describe what the system can *do* with World Model once it exists, and develop along a separate axis. A more capable system does not imply a different architecture, and a new architectural layer does not by itself grant a new capability. See [ADR-007 §6](ADR-007-memory-before-knowledge.md#6-relationship-to-the-capability-roadmap).

## 6. Core Building Blocks

- **Memory Entry** — a persisted, immutable raw observation. `RawDocument`, promoted. [ADR-007](ADR-007-memory-before-knowledge.md).
- **OCOMObject** — the source-agnostic representation of an ingested, interpreted record. `core/object.py`.
- **Concept** — a named unit of meaning something can be *about*. [OCOM Knowledge Model v0.1](OCOM-Knowledge-Model-v0.1.md).
- **Knowledge Fragment** — a unit of content with its own identity, independent of where it currently lives. [OCOM Knowledge Model v0.1](OCOM-Knowledge-Model-v0.1.md).
- **Relationship** — a typed, meaningful connection between two identified things. `core/object.py`, reused directly as Role Binding.
- **Evidence** — provenance, kept structurally separate from what it's evidence for. `core/evidence.py`.
- **Identity** — the decision that two records refer to the same real thing. `identity/resolver.py`.

## 7. Design Principles

- Knowledge is always derived from Memory, never the reverse. [ADR-007 §1](ADR-007-memory-before-knowledge.md#1-decision).
- Memory Entry is immutable once created. [ADR-007 §3](ADR-007-memory-before-knowledge.md#3-memory-entry).
- No claim without traceable Evidence. [Architecture-Status-v0.1.md](Architecture-Status-v0.1.md), "Evidence-first reasoning."
- Knowledge and World Model are always recomputable, never a second source of truth. [ADR-007 §4](ADR-007-memory-before-knowledge.md#4-invariants).
- Capability growth never requires Memory to change. [ADR-007 §6](ADR-007-memory-before-knowledge.md#6-relationship-to-the-capability-roadmap).
- The Reader adapts to OCOM; OCOM never adapts to the Reader. [`README.md`](../../README.md).

## 8. Document Map

Read in this order:

1. **This document** — orientation.
2. **[ADR-007](ADR-007-memory-before-knowledge.md)** — the current foundational decision; everything else assumes it.
3. **[OCOM Knowledge Model v0.1](OCOM-Knowledge-Model-v0.1.md)** — what Knowledge is made of.
4. **[Architecture-Status-v0.1.md](Architecture-Status-v0.1.md)** — what of the above actually has code today versus exists only as a decision.
5. **[MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md)** and other `MILESTONE-*-DESIGN.md` documents — the detailed design behind each layer.
6. **`src/ocom_reader/`** — the implementation, once the design that motivates a given piece of it is understood.

## 9. Current Status

Stable, implemented, and unchanged since introduction: `OCOMObject`, `Evidence`, the Adapter/Normalizer/Storage separation, the deterministic Reader MVP (M001-M010), the optional LLM layer (M019). Decided but not yet implemented: Memory Entry, the Knowledge Model, Expert Phase 1 (Intent/Audience/Reasoning). Not yet designed: World Model construction itself. This list is a pointer, not the record — [Architecture-Status-v0.1.md](Architecture-Status-v0.1.md) is the authoritative, actively maintained breakdown; this document does not duplicate it and will not be kept in sync line-by-line with it.

## 10. Future Direction

The immediate next step is implementing what ADR-007 already decided — a working Memory layer — before any further design work assumes it exists in code. Beyond that, capability growth (toward Expert, then Observer) and source breadth (beyond documentation) are expected to proceed together, gated by each other rather than in either order alone. No detailed plan is recorded here; this section exists only to say which direction is next, not to plan it.
