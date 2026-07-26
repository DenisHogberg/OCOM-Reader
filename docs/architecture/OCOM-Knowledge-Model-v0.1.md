# OCOM Knowledge Model v0.1 — Architecture

**Status:** Draft — architecture proposal, nothing in this document has been implemented.
**Date:** 25 July 2026
**Builds on:** [MILESTONE-020-DESIGN.md](MILESTONE-020-DESIGN.md) (OCOM Expert Phase 1), [MILESTONE-019](MILESTONE-019.md) (Optional LLM Layer), the Reader/Evidence separation established since [MILESTONE-001](MILESTONE-001.md).
**Consequence for MILESTONE-020-DESIGN.md:** that document's `KnowledgeItem`/`KnowledgeSelection` sketch predates this model and uses its own ad hoc shape (a `kind` field distinguishing `specification-evidence`/`expert-knowledge`). Once this document is approved, that sketch should be reconciled against the vocabulary defined here rather than left standing as a second, parallel shape. Not done in this document — named so it isn't silently forgotten.
**Consequence of ADR-007:** that ADR fixes what everything in this document is ultimately built from — Knowledge (Concept, Fragment, Role Binding) is always derived from Memory, never from a source directly. §3's `Source` primitive, defined below as "where a Fragment's content currently physically resides," is what a Fragment's Memory Entry (`source` + `source identifier`, per ADR-007) resolves to once Memory exists as a persisted stage. This document's own primitives are unchanged by ADR-007 — only where they get their input is now fixed.

## 1. Purpose

Every architectural question this project has run into over the last
few design rounds — where is a term canonically defined, is this
passage a definition or a mention, which of two documents is the
Source of Truth, how do Expert Knowledge and the Specification relate —
turned out to be the same question asked from different angles: **what
does OCOM Reader consider a unit of knowledge, and what can it know
about that unit, independent of how or where that unit happens to be
stored today?**

Nothing in this codebase currently answers that question as data.
Reader answers it today by re-deriving structure from Markdown shape
at read time — grepping headings, reading whole documents, applying
heuristics — which is exactly why two real, undetected inconsistencies
(a duplicated `Domain` definition, a `Relationship` participant
mismatch) sat in the Specification until a human read enough of it by
hand to notice.

This document defines the **Knowledge Model**: the small set of
primitives that answer "what is a unit of knowledge, what can be known
about it, and where does it currently live" — independent of Registry,
Retrieval, Expert Knowledge, Company Knowledge, or any reasoning
pipeline built on top. Those are all *consumers* of this model, not
part of it, and none of them are designed here.

## 2. Scope Boundary

This document defines four primitives and the relationships between
them. It deliberately does not define:

- **Semantic Registry** — an access/index layer over this model (Concept
  → Role lookups, conflict detection). A consumer, designed separately.
- **Retrieval Index** — a different access/index layer over this model
  (Source/text-level search). Already exists (M006-M010); how it comes
  to consume this model is a separate, later question.
- **Expert Knowledge** — a *population* of this model (Fragments tagged
  non-normative), not a structurally distinct layer. What content goes
  in is an authoring question, out of scope here.
- **Company Knowledge** — a future extension of this model's Concept
  namespace to per-organization scope. Not designed here.
- **Reasoning Pipeline** — how Intent/Audience/Expert Reasoning consume
  knowledge (already sketched in `MILESTONE-020-DESIGN.md`). This
  document only supplies the vocabulary that sketch should eventually
  be reconciled against.

This document also contains **no code, schema, or class definitions**,
deliberately, not as an oversight. A model whose description already
commits to a representation (a Python class, a JSON shape) has quietly
stopped being medium-independent, which is the property §5 depends on.

## 3. The Four Primitives

**Concept** — a named unit of meaning in OCOM's own vocabulary (Domain,
Object, Organization, Relationship...). A Concept has identity but no
content of its own — it is what things are *about*, never itself a
piece of text. Concepts may relate to each other (e.g. "Organization is
a specialization of Object") — that relationship is itself expressible
using this same model, not a separate mechanism.

**Knowledge Fragment** — a unit of content with its own stable
identity, independent of any Concept it happens to be about and
independent of where it currently lives. A Fragment is what carries
meaning; a Concept is what that meaning is about. Collapsing these two
was the specific mistake in this project's own prior draft of this idea
(treating "Document" as the atomic unit conflated Fragment-identity
with Source-location, and quietly broke medium independence before it
was named as a goal).

**Role Binding** — a labeled edge connecting a Concept to a Knowledge
Fragment: *this Fragment plays this role for this Concept.* Not a
layer above or below the other two — the relationship between them,
carrying a role classification along two independent axes (see §4).
Modeled as an edge, not a chain link, because the cardinality is real:
one Fragment may legitimately bind to more than one Concept (a passage
explaining "a Domain governs Entities" is evidence for both), and one
Concept accumulates many Role Bindings over its Fragments.

**Source** — where a Fragment's content currently physically resides: a
file path, a URL, a database row, a paragraph inside a `.docx`. Source
carries no interpretive weight and answers no question about meaning —
only "where do I currently go to read this." A Fragment has exactly
one current Source (its origin may change over time; that is a Fragment
gaining a new Source record, not a new Fragment). Per [ADR-007](ADR-007-memory-before-knowledge.md),
Source is not the original external system directly — it resolves to
the Fragment's Memory Entry, which is what actually persists origin.

## 4. Role Binding — Two Independent Axes

A Role Binding is not a single label; it is two independent
classifications, each answering a different question:

- **Normative Status** (how authoritative): `Canonical` / `Supporting`
  (elaborates a Canonical Fragment without redefining it) /
  `Non-normative` (mentions the Concept without defining it) /
  `Governance-record` (rationale or decision about the Concept, not
  itself a definition).
- **Content Genre** (what kind of content): `Definition` /
  `Property-reference` / `Example` / `Tutorial` / `FAQ` / `Rationale` /
  `Comparison`.

Keeping these independent is what lets "is this a Definition or a
Property?" and "is this normative or an example?" be answered as two
separate, settable facts instead of one enum trying to carry both —
the same shape of separation `MILESTONE-020-DESIGN.md` already applies
to Intent and Audience. That's not a coincidence worth ignoring: this
project has now independently rediscovered the same "these look like
one dimension but are two" pattern twice, which is a reasonable signal
it's a sound general habit, not a one-off fix.

## 5. Independence from Medium

Two different strengths of independence, and this document commits to
only one of them:

- **Weak independence** (identity + classification) — Concept identity
  and Role Bindings are fully medium-independent today: "this Fragment
  is the Canonical Definition of Domain" is a fact about meaning, true
  regardless of what file currently holds the text. This is what this
  document defines.
- **Strong independence** (content itself) — would require a Fragment's
  actual text to be captured into the model's own store rather than
  always dereferenced through its current Source. Not adopted here.
  This project already has a deliberate, existing precedent *against*
  duplicating content into its models: `Evidence.reference` is a
  pointer, not a copy, and MILESTONE-019 explicitly kept raw file
  content out of what ever leaves the process toward an LLM provider,
  for staleness and security reasons. Reversing that would be a real,
  separate architectural decision — not something this document adopts
  by default, and not something that should happen as a quiet side
  effect of wanting a Knowledge Model.

**Litmus test for whether this separation is real:** re-platforming the
underlying content store — Markdown today, a website or database
tomorrow — should touch only Source records. Concept identity, Fragment
identity, and Role Bindings should require zero changes. This is the
acceptance criterion for any future implementation of this model, not
just an aspiration.

This is the same principle already stated in this repository's own
`README.md` — "the Reader adapts to OCOM, OCOM never adapts to the
Reader" — extended one level further: **the Knowledge Model adapts to
wherever content currently lives; content location never shapes the
Knowledge Model.**

## 6. Relationship to Existing OCOM Concepts

This model is not invented independently of OCOM's own architecture —
it is the same discipline OCOM already applies, pointed at OCOM's own
documents:

- `Meta/Relationship.md` (canonical Specification) distinguishes
  Relationship (conveys business meaning) from Reference (mere
  connectivity). Role Binding is that same distinction, applied to
  knowledge about documents instead of business Objects.
- `Meta/Registry.md` already defines Registry as "a governed collection
  of identifiable Objects... establishes authoritative sources." A
  future Semantic Registry consuming this model is a direct instance of
  that existing concept — not a new one competing with it.
- This codebase's own `Evidence`/`OCOMObject` separation (provenance
  kept structurally apart from the thing it's evidence for, since
  MILESTONE-001) is the same shape as Source/Fragment separation here,
  one level up the stack.

None of this is decorative. It's evidence that the model fits the
system it's describing, rather than being a new idea layered on top of
an unrelated one.

## 7. What Becomes Possible on Top (Not Designed Here)

Each of the following becomes a consumer of this one model rather than
a system needing its own reconciliation with the others. Naming them
is not designing them:

- **Semantic Registry** — an index answering Concept → Role Binding
  lookups, including automatic detection of Normative Status conflicts
  (more than one `Canonical`/`Definition` binding for the same Concept
  — the exact shape of the Domain divergence already found by hand).
- **Retrieval Index** — an index answering Source/text-level relevance
  queries. Already exists (M006-M010); becomes one more view over this
  model rather than a separate system to merge with it.
- **Expert Knowledge** — simply the set of Fragments whose Role Bindings
  carry `Non-normative` status with genres like `Rationale` or
  `Comparison`. Not a separate store.
- **Company Knowledge** — a later extension giving Concepts a
  per-organization namespace, reusing the same four primitives rather
  than inventing new ones.
- **Reasoning Pipeline** (`MILESTONE-020-DESIGN.md`'s Intent/Audience/
  Knowledge Selection/Expert Reasoning stages) — consumes Role Bindings
  filtered by Normative Status and Content Genre, in place of that
  document's current ad hoc `KnowledgeItem` shape.

## 8. Naming Note

"Registry" already names two different things in this workspace before
this document existed: `Meta/Registry.md` (a normative Specification
concept about Objects generally) and this repository's own `registry/`
package (M007, "pointer-only knowledge graph over the index"). A future
access layer over this model does not need to win a new, grand name —
it only needs a name for *one particular index*, since the model itself
is now the foundational thing. That materially lowers the naming
pressure flagged in the prior design discussion; the actual choice is
still the Architect's, not decided here.

## 9. Open Questions for the Architect

- **Strong independence** (§5) — worth adopting later, or does the
  existing no-content-duplication precedent stand as-is indefinitely?
- **Role vocabulary extensibility** — are the Normative Status and
  Content Genre value sets closed for Phase 1, or explicitly extensible
  (the way OCOM's own Relationship Types are)?
- **Concept namespace scope** — is "Concept" global by default with
  Company Knowledge as a later namespace extension (as assumed in §7),
  or should namespace-scoping be part of the Concept primitive from the
  start?

## 10. Explicitly Not Designed Here

Semantic Registry's query/index design, Retrieval's integration with
this model, Expert Knowledge's authoring process and content, Company
Knowledge's namespace mechanics, and the Reasoning Pipeline's
consumption of Role Bindings are all separate, subsequent design
efforts, each building on this document once it's approved — not
implied or pre-decided by anything above.
