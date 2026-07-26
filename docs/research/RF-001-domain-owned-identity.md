# Research Finding RF-001: What Makes an Entity an OCOM Object

**Status:** Research Finding — not an ADR, not binding on OCOM Reader's own architecture. A candidate input to the canonical OCOM Specification's own governance process (Reference Case → Observation → ADR Candidate → Architecture Review), not itself a decision.
**Date:** 2026-07-26
**Scope:** Tested against infrastructure (VPS, Service, Certificate, Deployment...) and a business domain (Affiliate, Payment, Campaign...) as neutral test-beds — this finding is not itself an infrastructure or Reader design decision.

## The Question

While designing OCOM Reader's own production infrastructure, an observation surfaced: `Service` behaves like a genuine OCOM Object, `Container` does not — it is only `Service`'s current implementation. Generalized, this suggested a hypothesis worth testing rigorously rather than adopting on intuition: is there a fundamental criterion for what qualifies as an OCOM Object, beneath the six characteristics (Identity, Lifecycle, Relationships, Ownership, Events, Governance) OCOM already uses?

## Hypothesis 1: Stable Operational Identity — did not survive as a universal law

The first formulation: an entity is an OCOM Object only if its identity survives a change of implementation (a Service remains the same Service whether run under Docker, Kubernetes, or a bare process).

This held for Service, Domain, Concept, VPS. It failed on direct counterexamples that are not edge cases but already-accepted, working parts of OCOM's own model:

- **Event** — the test asks whether an event's identity survives "reimplementation." The question is malformed for an event: an event does not get reimplemented, it is a fact, tied to its one occurrence.
- **Memory Entry** — built in this project's own M021, with `id` deliberately derived from content hash. A differently-worded record of arguably the same underlying observation produces a different id, by design (ADR-007's Evidence-first discipline), not by oversight. Stable-Operational-Identity would call this a defect; it is the opposite.
- **Payment** (a business-domain instance, not the category) — a specific payment cannot be "reimplemented" under a different PSP; once it happened, it happened through whichever PSP processed it. What is implementation-independent is the *category* "Payment," not a specific instance's identity — a distinction the original hypothesis did not draw.

None of these are wrongly-classified objects. They are objects for which the test itself asks the wrong question. Stable Operational Identity is real and useful, but only for one part of the object space, not as a universal law.

## Hypothesis 2: continuant/occurrent — also did not survive

The natural repair was to split objects into two ontological kinds — continuants (survive reimplementation, Stable-Operational-Identity applies) and occurrents (facts tied to their occurrence, an Evidence-style test applies instead) — and use the pair to explain which test governs which object.

Tested by deletion: removing the terms and checking what stops working in defining Object, building Lifecycle, building Memory, building Knowledge, or performing reasoning. Result: nothing. `ADR-007` (Memory), `OCOM-Knowledge-Model-v0.1.md` (Knowledge), and `MILESTONE-020-DESIGN.md` (Reasoning) were each built and fully justified without the terms ever appearing — they were introduced only afterward, as narration for decisions already made on other grounds.

The classification also failed to hold under its own author's use of it: Memory Entry was labeled "occurrent," but in the strict sense an occurrent is what unfolds and has no persistence at an instant (the meeting itself, while it happens) — Memory Entry is the opposite, an immutable record wholly present at every moment it exists, closer to a continuant. Conflating "the event" with "the record of the event" is exactly the kind of imprecision a load-bearing primitive should not permit even from careful use, and did.

Verdict: not adopted into OCOM Core. At most retained, outside the model, as an optional teaching metaphor — never as a criterion.

## What survived: Domain-Owned Identity

A single criterion explains Stable Operational Identity's successes without a prior ontological split: **an entity is an OCOM Object if and only if its identity is assigned by, and authoritative to, the domain or operational context that uses it — not the technical mechanism that currently realizes or records it.**

This explains why Container fails (identity assigned by and meaningful only to Docker's own bookkeeping) and why Service, Event, and Memory Entry all pass, by the same single test, without first sorting them into categories. It also explains why each of the six existing OCOM characteristics matters: Lifecycle, Ownership, Relationships, Events, and Governance are each only meaningful once something's identity is already owned by the domain — they are downstream consequences of this one criterion, not a parallel checklist.

## The deeper answer: operational role, not ontological type

The clearest evidence came from re-examining Certificate and Secret from the infrastructure test-bed. The same real entity took two different identity treatments depending on which operational question was asked of it — "is TLS coverage currently satisfied" (a standing, Stable-Operational-Identity-shaped question) versus "which specific certificate was issued and when" (a fixed-record question). The entity's category was never a fixed property of the thing itself; it changed with the operational question being asked.

This settles the main question directly: **role in the operational model is more fundamental than ontological type.** Type is not something an entity has independent of a system reasoning about it — it is a consequence of which operational question is currently being asked. Domain-Owned Identity asks that question directly ("whose authority is this identity under") and does not require a prior philosophical sort of the world to be answered.

## Status and Next Step

This is a research finding, not a decision. It does not change OCOM Reader's own architecture and introduces no new component. If it is to become part of OCOM Core, that requires the canonical Specification's own governance process — this document is written to be usable as input to that process (a Reference Case or ADR Candidate), not as a substitute for it.
