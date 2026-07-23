# Architecture Status v0.1

**Date:** 2026-07-23
**Purpose:** A single, current snapshot of what in this project's architecture is settled, what is still actively changing, what exists only as design, and which documents no longer fully describe the implementation. Produced by the Architecture Consistency Cleanup that followed the Architecture Consistency Review.
**This document decides nothing new.** It is a synchronization pass — every classification below is sourced from an existing ADR, milestone, or design document, or from direct comparison against the current code (`src/ocom_reader/`). No architecture changed to produce it.

## Stable Architecture

Confirmed across multiple documents and implementation phases, unchanged since introduced. Changing any of these requires a new ADR, not an edit.

- **`OCOMObject`** (`core/object.py`) — field set unchanged since [MILESTONE-001](MILESTONE-001.md).
- **`Evidence`** (`core/evidence.py`) — structurally separate from `metadata`, unchanged since introduced.
- **`Adapter` / `Normalizer` / `Storage` separation** ([ADR-001](ADR-001-normalizer-architecture.md)) — proven by two independent Normalizer implementations requiring zero core changes.
- **Metadata Namespaces** — `identity` / `attributes` / `technical` ([ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-004](ADR-004-metadata-namespace-migration.md)) — implemented in `identity/resolver.py` and both Normalizers; now load-bearing for [ADR-005](ADR-005-identity-resolution-signal-model.md), the Classification Engine, and Enrichment Provenance.
- **Append-only Enrichment history** ([OCOM-Enrichment-Provenance-v0.1.md](OCOM-Enrichment-Provenance-v0.1.md), reaffirmed by [ADR-006](ADR-006-classification-lifecycle-and-human-override.md)) — no overwrite, no separate versioning mechanism.
- **Evidence-first reasoning** — "no `MATCH` without `Evidence`," "no answer without `Evidence`," "surface conflicts, don't auto-resolve them." Stated independently and consistently in [OCOM Agent v0.1 Design §7](OCOM-Agent-v0.1-Design.md#7-evidence-handling), [OCOM-Identity-Resolution-v0.1.md §4](OCOM-Identity-Resolution-v0.1.md#4-evidence-requirements), [OCOM-Object-Intelligence-v0.1.md §7](OCOM-Object-Intelligence-v0.1.md#7-evidence-handling), and [ADR-005 §3](ADR-005-identity-resolution-signal-model.md#3-evidence-role) — the same principle, restated at each new layer, never contradicted.

## Experimental

Have real, tested code, but the architecture around them is still actively being revised — treat their current shape as provisional, not as a contract other components should build against yet.

- **Classification Engine** (`intelligence/classification.py`) — rule-based dictionary, working and tested, but [ADR-006](ADR-006-classification-lifecycle-and-human-override.md) and [OCOM-Enrichment-Provenance-v0.1.md](OCOM-Enrichment-Provenance-v0.1.md) already specify fields (`method`, `processor`, `status`) and conflict-handling behavior it doesn't have yet.
- **`IdentityResolver` scoring** (`identity/resolver.py`) — working and tested (`MATCH`/`NEW`/`UNCERTAIN`, namespace-aware per ADR-003), but [ADR-005](ADR-005-identity-resolution-signal-model.md) decided a three-band semantic model (identity-alone-sufficient / classification-as-fallback / identity-too-weak-to-rescue) that the actual scoring formula — one linear weighted sum, unchanged since before ADR-005 — does not yet implement. `IdentityResolver v0.2` is named, not built.

## Planned

Exist only as design — no code. Listed here so it's clear none of these should be assumed available.

- **Query Engine** — specified as a distinct component in [OCOM Agent v0.1 Design §3-4](OCOM-Agent-v0.1-Design.md#3-components); never built. `agent/registry.py`'s `find_candidates(query)` absorbs search directly instead.
- **`OCOMAgent` facade** (`ingest()` / `ask()`) — specified in the same document; never built. Every test wires `Query`/`Registry`/`EvidenceAggregator`/`AnswerComposer` together manually.
- **Relationship Intelligence** — specified in [OCOM-Object-Intelligence-v0.1.md §5.2](OCOM-Object-Intelligence-v0.1.md#52-relationship-intelligence); no code exists. Also has a self-acknowledged, still-unresolved circular dependency with Identity Resolution (§8/§11 of that document) that needs a design answer before implementation, not just an implementation task.
- **Attribute (Enrichment) Intelligence** — specified in [OCOM-Object-Intelligence-v0.1.md §5.3](OCOM-Object-Intelligence-v0.1.md#53-structured-attribute-enrichment); no code exists. `intelligence/classification.py` writes directly to `metadata["attributes"]["classification"]` itself rather than depending on a separate Attribute Enrichment component.
- **`IdentityResolver v0.2`** (ADR-005's three-band model, with real numeric thresholds) — semantics decided, numbers explicitly not — see Experimental above.
- **`method` / `processor` / `status` enrichment provenance fields** — fully specified in [OCOM-Enrichment-Provenance-v0.1.md §6](OCOM-Enrichment-Provenance-v0.1.md#6-consequences--what-this-implies-for-existing-code) and [ADR-006 §6](ADR-006-classification-lifecycle-and-human-override.md#6-consequences--what-this-implies-for-existing-code); not implemented.
- **`agent/registry.py` namespace migration** — `_searchable_text()` still scans all of `metadata` unfiltered; flagged as pending in [ADR-003](ADR-003-metadata-semantic-boundary.md#consequences), [ADR-004](ADR-004-metadata-namespace-migration.md#4-compatibility-impact), and [ADR-006](ADR-006-classification-lifecycle-and-human-override.md#5-impact-on-agent-and-identity-resolution) three times, fixed zero times. Which namespaces `Registry` should read was deliberately left as "Registry's own future decision," so this is a design question first, an implementation task second.

Note: `Relationship Intelligence` is listed only here, not under Experimental — it has no code at all, unlike Classification Engine and `IdentityResolver`, which are experimental precisely because they *do* have working implementations still subject to revision.

## Historical Documents

Documents that remain part of the project's record but no longer fully describe the current implementation. This is different from a Milestone's normal "Frozen" status — milestones are deliberately dated snapshots and were never meant to describe "now"; the documents below were originally written as forward-looking specs, and parts of them have since been superseded by what was actually built without that being marked, until this cleanup.

- **[OCOM-Agent-v0.1-Design.md](OCOM-Agent-v0.1-Design.md)** — §3 (Components) and §4 (Interfaces) are superseded by implementation (package layout, method signatures, and data shapes all differ from what was built); §1, §2, §5 (partially), §7, §8, §9 remain valid; §6 is superseded by later ADRs; §10 is mixed. See the section-status table added at the top of that document for the per-section breakdown.
- **[OCOM-Identity-Resolution-v0.1.md](OCOM-Identity-Resolution-v0.1.md)** — §2's `ResolutionRequest`/`ResolutionContext` batch contract and the fuller `IdentityDecision` shape were not implemented; a simpler, pairwise contract was built instead. See the "Implementation Status" section added to that document for the full breakdown. §1, §3–§7 remain accurate.
- **[OCOM-Object-Intelligence-v0.1.md](OCOM-Object-Intelligence-v0.1.md)** — §5.4's worked example used a classification-record shape (`metadata["attributes"]["classification_confidence"][tag]`) later replaced by a different, incompatible shape (`metadata["attributes"]["classification"] = [...]`) when Classification Engine was designed. Corrected in place with a note; the rest of the document (§1–§4, §5.1–§5.3, §6–§11) remains accurate design, none of it implemented beyond Classification Engine.

**Not included here:** [MILESTONE-001](MILESTONE-001.md), [MILESTONE-002](MILESTONE-002.md), [MILESTONE-003](MILESTONE-003.md), and [ADR-001](ADR-001-normalizer-architecture.md) through [ADR-006](ADR-006-classification-lifecycle-and-human-override.md) are not listed as historical in this sense. Milestones are explicitly frozen snapshots by design (accurate for the date on them, not claims about "now"). The ADRs' decisions all remain accepted and, where not yet implemented, say so themselves (see Experimental/Planned above) — none of them make a claim about the code that the code now contradicts.
