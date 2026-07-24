# MILESTONE-007 (Design): Knowledge Registry Architecture

**Status:** Draft — architecture only. Nothing in this document has been implemented. No code, no tests, no commits were made to produce it.
**Date:** 2026-07-23
**Builds on:** [MILESTONE-006](MILESTONE-006.md) (Repository Indexer), [MILESTONE-005](MILESTONE-005.md) (Runtime v0.2 Reliability Freeze), [MILESTONE-003](MILESTONE-003.md) (Identity Resolution Experiment Findings)

## Objective

Define, before any code is written, how `RepositoryIndex` data
(MILESTONE-006 — file paths, titles, headings, links) becomes a
Knowledge Registry: a structured representation of the named things
this repository's documentation describes (Concepts, Components,
Specifications, ADRs, Documents) and how they relate — without LLM
reasoning, and without accidentally rebuilding the exact problem
[MILESTONE-003](MILESTONE-003.md) already spent an entire experimental
arc proving is hard.

## Required Questions

### 1. Responsibility boundary: Repository Index / Knowledge Registry / Retrieval Engine

- **Repository Index (M006)** is file-and-structure aware, not
  meaning-aware. It knows a file exists, what it's titled, what
  headings it has, and what raw links it contains. It has no concept
  of "this document is *about* X" — only "this document *is* at path
  Y and *links to* path Z."
- **Knowledge Registry (this design)** is the layer where documents
  (and, conservatively, their headings — see §Data Model) become
  addressable, named entities, and where the *kind* of relationship
  between two entities gets a label, not just "a link exists." It
  operates one level of abstraction above the Index, but is still
  fully deterministic and mechanical — it does not read prose to
  understand it.
- **Retrieval Engine (future, not this milestone)** answers a query
  by finding and ranking relevant Registry entries. It depends on the
  Registry; the Registry does not depend on it. Not designed here —
  see §Non-Goals.

### 2. Which data belongs permanently inside the Registry?

The set of recognized entities (`RegistryEntry`) and the labeled
relationships between them (`KnowledgeRelation`). Nothing about a
document's *content* — that stays in the Index (§3). A Registry entry
holds a pointer to its source Index entry, never a copy of its title,
headings, or preview.

### 3. Which data should remain inside the Repository Index?

Everything content- and file-shaped: `path`, `last_modified`,
`content_hash`, the raw `headings` list, the unfiltered
`outbound_references`, `invalid`/`duplicates` bookkeeping. This is the
same "pointer, not copy" boundary already enforced between `Evidence`
and `OCOMObject.metadata` since this project's very first milestone —
applied here between `KnowledgeRegistry` and `RepositoryIndex` instead.
Duplicating Index content into the Registry would let the two drift
out of sync with no way to detect it — named explicitly as a risk in
§Risks.

### 4. Which future components should depend on the Registry?

A future **Retrieval Engine**, and, plausibly, a future
**documentation-facing Answer Composer** — but see the important
caveat in §Component Boundaries: this is very likely *not* the same
`AnswerComposer` already in `agent/answer.py`, because that one is
built for a different subject matter entirely (see next question).

### 5. Which components must remain independent?

- `core/`, `interfaces/`, `storage/` — untouched by this design, as
  required.
- The entire OCOM object-reasoning track — `adapters/`, `normalizers/`,
  `identity/`, `intelligence/`, `agent/`, `runtime/*` — must neither
  depend on the Registry nor be depended on by it. **These two tracks
  describe different subject matter**: the object-reasoning track
  represents OCOM *domain* objects a source produces (e.g. an
  "Affiliate Manager" role, per every worked example since
  [MILESTONE-003](MILESTONE-003.md)); the Registry represents *this
  project's own architecture documentation* (ADRs, Milestones, design
  docs). They are structurally similar — both eventually need
  identity, evidence, and relationships — but conflating them because
  the shapes rhyme would be a mistake, not an economy.
- **Repository Index must never depend on the Registry.** The Index
  was built and frozen in M006 as a self-contained, independently
  useful artifact; the Registry is a consumer of it, not a peer.

## Registry Responsibilities

**Owns:**

- The catalog of recognized `RegistryEntry` nodes and the labeled
  `KnowledgeRelation` edges between them.
- The rule for turning one `RepositoryIndex` state into one Registry
  state (deterministic, rebuildable from scratch — see §Design
  Principles).
- A small, fixed, explicit vocabulary for `entry_type` and
  `relation_type` — extensible by adding new *values*, not by changing
  *code*, the same discipline already used for `Relationship.
  relationship_type` (`core/object.py`) and `intelligence/
  classification.py`'s dictionary.

**Does not own:**

- Document content (title, headings, preview — Index's job).
- Search, ranking, or relevance scoring (Retrieval Engine's future
  job).
- Answer composition (a future, separate component's job).
- Any inference about what a document *means* beyond what its own
  structure (title, headings) and this repository's own existing
  structural conventions (see §Data Model, relation-type detection)
  already state explicitly.

## Data Model

Names below are illustrative, per the task's own instruction — not
claimed final.

```python
class RegistryEntry:
    id: str                    # stable, e.g. the source document's Index id
    name: str                  # display name — the document's title, verbatim
    entry_type: str            # "Document" | "ADR" | "Milestone" | "Architecture" | "Concept" | "Component" | "Specification"
    source_document_id: str    # pointer into RepositoryIndex — never a content copy
    aliases: list[str] = []    # known alternate names, data not schema (same pattern as
                                # OCOM-Agent-v0.1-Design.md's metadata["aliases"] proposal)

class KnowledgeRelation:
    source_id: str
    target_id: str
    relation_type: str         # fixed vocabulary — see below
    evidence_link: str         # the Index-level link (internal_links entry) this relation was derived from

class KnowledgeRegistry:       # "RegistryGraph" in the task's own naming — container + query surface
    entries: list[RegistryEntry]
    relations: list[KnowledgeRelation]
```

**On `entry_type` and the temptation to over-populate it:** the type
vocabulary intentionally includes `Concept`/`Component`/`Specification`
— per the task's own goal — but **v0.1's population rule is
conservative on purpose**: every `RegistryEntry` in v0.1 corresponds
1:1 with a `RepositoryIndex` document (`entry_type` mirrors
`DocumentIndexEntry.document_type` directly: `ADR`→`ADR`,
`Milestone`→`Milestone`, etc.), optionally extended with one entry per
top-level heading within a document (since headings are already
extracted, deterministic, zero additional inference). **Recognizing a
`Concept` or `Component` that is *mentioned* across several documents
but has no document of its own — e.g. realizing "IdentityResolver" is
one Component referenced by five different ADRs — is explicitly not
solved by this design.** That requires deciding a mention of a term in
prose refers to the same named thing as another mention elsewhere,
which is exactly the "same real-world thing, described differently"
problem [MILESTONE-003](MILESTONE-003.md) already spent an entire
experimental arc proving deterministic, non-interpretive methods
handle poorly (and [ADR-005](ADR-005-identity-resolution-signal-model.md)
subsequently built real machinery around, still incomplete). Rebuilding
that problem casually, one level up, inside the Registry — under the
excuse that "it's just grouping mentions, not really reasoning" — is
named here as the single biggest risk this design exists to head off
(§Risks). `Concept`/`Component` remain real, valid schema values for
when a validated mechanism exists to populate them; v0.1 does not
claim to have one.

**Relation-type detection — grounded in a real, existing convention,
not invented for this design:** every document in this project's own
`docs/architecture/` already carries a structured `**Builds on:**` line
in its header (confirmed present, exactly once, in all 16 documents
checked). A link appearing in that specific, structurally-recognizable
position can be deterministically labeled `relation_type="builds_on"`
— a fixed-pattern match, the same kind of mechanical rule already used
for `intelligence/classification.py`'s keyword dictionary, not
inference. Links found anywhere else in a document's body default to
the generic `relation_type="references"`. A `"supersedes"`/
`"superseded_by"` relation is a plausible second case (some documents,
e.g. [OCOM-Agent-v0.1-Design.md](OCOM-Agent-v0.1-Design.md)'s Section
Status table, already say this explicitly) but its structure is less
uniform across documents than `**Builds on:**` is — named as an open
question (§Open Questions), not committed to for v0.1.

## Public API

Illustrative signatures only — no implementation, per this task's
constraints:

```python
class KnowledgeRegistry:
    def lookup(self, entry_id: str) -> Optional[RegistryEntry]: ...
    def find(self, name_or_alias: str) -> list[RegistryEntry]: ...
    def by_type(self, entry_type: str) -> list[RegistryEntry]: ...
    def neighbors(self, entry_id: str) -> list[RegistryEntry]: ...
    def related(self, entry_id: str, relation_type: str) -> list[RegistryEntry]: ...
    def resolve(self, reference: str) -> Optional[RegistryEntry]: ...
```

**`resolve()` is flagged as the highest-risk method in this surface.**
Its name evokes exactly what `IdentityResolver` does — turning an
ambiguous reference into a canonical identity — and that is precisely
the kind of decision this design must not quietly re-implement inside
a "helper" method. In v0.1, `resolve()` must mean only exact,
mechanical matching (a literal path, a literal id, a literal alias) —
never fuzzy or similarity-based matching. If it ever needs to become
more capable than that, that is a decision for its own ADR, informed
by its own validation experiment — the same sequencing every
capability in this project has followed, not an exception made quietly
inside a Registry method.

## Component Boundaries

```
Repository Index (M006, frozen)
        │  read-only
        ▼
Knowledge Registry (this design)
        │  read-only
        ▼
Retrieval Engine (future — not this milestone)
        │
        ▼
Answer Composer (future, documentation-facing — likely NOT
                  agent/answer.py's AnswerComposer; see below)
```

**Whether the documentation-knowledge track (Index → Registry →
Retrieval → Answer) ever converges with the existing OCOM
object-reasoning track's answer composition
(`agent/answer.py`'s `AnswerComposer`) is an open question, not decided
here.** They could plausibly converge later — e.g. both eventually
producing `Evidence`-shaped citations reusing `core/evidence.py` — or
they could remain permanently separate, since their subject matter is
different (§Required Question 5). Assuming either answer now would be
a guess; it is named in §Open Questions instead.

## Design Principles

- **Determinism.** Given the same `RepositoryIndex` state, the
  Registry build produces byte-identical entries and relations every
  time — the same guarantee M006 already established for the Index
  itself, propagated one layer up, verified the same way (build twice,
  compare).
- **Reproducibility.** The Registry is *built* from Index state, not
  incrementally mutated — no partial-update path, no hidden state
  between builds. Same "rebuild from scratch" pattern M006 already
  uses (and already named as a scale limitation to accept, not solve,
  in MILESTONE-006).
- **Separation of concerns.** Registry never stores content (pointer
  only), never searches or ranks (Retrieval Engine's job), never
  composes answers. Each responsibility stays where the component
  boundary in §2 puts it.
- **Testability.** Every population rule (document → entry,
  `**Builds on:**` line → relation) is a fixed, mechanical
  transformation, testable in isolation against synthetic
  `RepositoryIndex` fixtures — the same two-tier testing discipline
  (synthetic fixtures + one real-repository integration test) M006
  already established and this design inherits rather than reinvents.
- **Future extensibility.** `entry_type` and `relation_type` are open,
  small, string-based vocabularies, not hardcoded enums entangled with
  control flow — adding a new type later is a data change, matching
  the same pattern `classification: list[str]` on `OCOMObject` already
  uses successfully.

## Risks

- **Overloading the Registry.** The single biggest temptation:
  quietly letting the Registry also do a bit of search, a bit of
  ranking, a bit of answer phrasing, because it's "right there." This
  is the exact failure mode `agent/registry.py` was rescued from across
  three separate hardening milestones (M004→M006's Runtime v0.2 arc) —
  keep the Registry a pure structural store, full stop.
- **Hidden reasoning.** Named concretely in §Public API (`resolve()`)
  and §Data Model (`Concept`/`Component` population) — the risk is not
  hypothetical, it is exactly where this design's own API surface
  would make it easy to smuggle in fuzzy matching under an innocuous
  method name.
- **Duplication of Repository Index.** If `RegistryEntry` ever starts
  caching a document's title or headings instead of pointing at the
  Index's copy, the two will drift the moment a document changes and
  only one side is rebuilt — the same class of problem `Evidence`
  vs. `metadata` separation was designed to prevent from this
  project's first milestone onward.
- **Cyclic dependencies.** The dependency chain in §Component
  Boundaries is strictly one-directional: Index ← Registry ← Retrieval
  ← Answer. Any future change that has the Index reading the Registry,
  or the Registry reading the Retrieval Engine, breaks this and must
  be treated as a design regression requiring its own ADR to justify,
  not a convenient shortcut.
- **Premature entity extraction disguised as structure.** A
  Concept/Component extractor that scans prose for capitalized terms
  or repeated phrases would *look* mechanical and rule-based (like
  `intelligence/classification.py`'s dictionary) while actually making
  the same kind of ungrounded judgment call
  [MILESTONE-003](MILESTONE-003.md) already showed fails quietly. Any
  future step in that direction needs its own validation experiment,
  the same rigor Classification Engine got before it was trusted with
  even a three-rule dictionary — not a shortcut taken because it
  "seems safe."

## Acceptance Criteria

Before implementation of Knowledge Registry v0.1 may begin:

1. This document is reviewed and its Data Model (§Data Model) accepted
   — names may still change, but `RegistryEntry`/`KnowledgeRelation`
   as *concepts*, and the 1:1-with-Index-document population rule,
   must not be open questions anymore.
2. The `**Builds on:**` → `relation_type="builds_on"` detection rule
   is either accepted as specified (§Data Model) or explicitly replaced
   — not left ambiguous, since it is the one piece of this design with
   a concrete, implementable mechanism already proposed.
3. A first, concrete, falsifiable acceptance scenario is agreed —
   e.g. *"build a Registry from this repository's own Index; confirm
   ADR-003 has a `builds_on` relation pointing at
   OCOM-Object-Intelligence-v0.1 and MILESTONE-003"* — mirroring how
   every prior implementation milestone in this project started from a
   concrete, checkable scenario rather than an abstract goal.
4. No component outside a new `registry/`-equivalent package (or
   wherever this is eventually placed) needs to change to build it —
   confirmed by this design requiring only read access to
   `RepositoryIndex`, nothing else.
5. `Concept`/`Component` population remains explicitly deferred (§Data
   Model) — implementation must not quietly attempt it "since the
   schema already supports it."

## Non-Goals

Explicitly excluded, per the task:

- Production code, tests, or commits — none exist as a result of this
  document.
- Entity extraction from prose (recognizing a `Concept`/`Component`
  mentioned across documents without a document of its own).
- Object recognition — not to be confused with, and not a return to,
  `intelligence/classification.py`'s OCOM object classification; this
  is a different track entirely (§Required Question 5).
- Graph construction beyond the flat `entries`/`relations` lists
  described here — no graph database, no traversal algorithms beyond
  the simple `neighbors()`/`related()` lookups sketched in §Public API.
- LLM integration of any kind.
- The Retrieval Engine itself.
- Answer generation of any kind.

## Open Questions

1. **Does the documentation-knowledge track (Registry → Retrieval →
   Answer) ever converge with the OCOM object-reasoning track's answer
   composition (`agent/answer.py`)**, or do they remain permanently
   separate systems that happen to share design patterns? Not decided
   (§Component Boundaries).
2. **Is a `"supersedes"`/`"superseded_by"` relation type worth a
   dedicated v0.1 detection rule**, given its structure is less
   uniform across existing documents than `**Builds on:**`, or should
   it wait for a second, cleaner convention to emerge? Left open.
3. **Where does the Registry package physically live** —
   `src/ocom_reader/registry/`, or nested under `indexer/` as a
   consumer? Not decided; naming and placement were explicitly left
   open by this task ("do not assume these names are final").
4. **What triggers a Registry rebuild** — every read (matching M006's
   own no-incremental-indexing limitation), or some other cadence?
   Inherited as an open question from MILESTONE-006, not newly
   introduced here, and not resolved by this design either.
5. **Should `KnowledgeRelation` be directional-only, or should some
   relation types (e.g. a plain `"references"`) also expose a
   symmetric view via `neighbors()`** regardless of direction? Sketched
   informally in §Public API (`neighbors()` implies both directions,
   `related()` implies direction matters) but not rigorously specified.
