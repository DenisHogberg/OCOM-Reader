# MILESTONE-020: OCOM Expert — Phase 1 (Intent, Audience, Expert Knowledge) — Design

**Date:** 25 July 2026
**Status:** Design — architecture proposal, implementation not started.
**Builds on:** [MILESTONE-019](MILESTONE-019.md) (Optional LLM Layer), [MILESTONE-009-010](MILESTONE-009-010.md) (Reader/Composer), [ADR-007](ADR-007-memory-before-knowledge.md) (Knowledge is always derived from Memory — fixes what Knowledge Selection's inputs are ultimately built from; does not change this document's own pipeline)
**Supersedes:** the "M020 Product Release" placeholder in [MILESTONE-019.md](MILESTONE-019.md)'s Roadmap — redirected to this scope by explicit author direction, 25 July 2026. Recorded here rather than silently overwritten.

## Objective

OCOM Expert Phase 1: an AI that understands OCOM deeply enough to explain,
compare, defend, teach, and advise on it for any audience — before it ever
attempts to model a specific customer organization (Company Intelligence,
explicitly out of scope here).

This milestone is a **design document only**. No code is written or
implied to exist by this document.

## Scope Boundary — What M020 Is Not

- **Not a deeper model of the Specification.** The canonical OCOM
  Specification (`/Users/mac/Downloads/OCOM`) remains the sole normative
  source. Nothing in this milestone introduces a second, competing model
  of OCOM's concepts.
- **Not Comprehension Detection.** No user modeling, no conversation
  memory, no adaptive learning across turns. Phase 1 is stateless per
  Question — deferred to a later milestone as a substantially larger,
  separate capability.
- **Not Company Intelligence.** Reasoning about a specific customer's own
  organization, documents, or terminology is out of scope.

## Pipeline

```
Question
    ↓
Intent Analysis
    ↓
Audience Analysis
    ↓
Knowledge Selection
    ↓
Expert Reasoning
    ↓
Answer Composition
    ↓
Interaction Layer
```

Each stage is described below. The existing M001-M019 pipeline
(`Reader → Retrieval → Composer → ComposedAnswer → LLMAdapter`) is not
replaced — Knowledge Selection reuses it unchanged as one of its two
sources (see below).

## Expert Knowledge Base — A Separate Explanatory Layer, Not a Deeper Specification

The Expert Knowledge Base holds content that intentionally does **not**
belong in the Specification: rationale, comparisons against other
approaches (DDD, ERP, BI), teaching material, analogies, and
audience-specific framings of existing Specification concepts.

Proposed two-source model for Knowledge Selection:

1. **Specification-grounded Evidence** — the existing deterministic
   Retrieval/Registry/Composer pipeline, unchanged, pointed at the
   canonical OCOM Specification repository. This remains the only source
   for normative, factual claims about what OCOM *is*.
2. **Expert Knowledge Base entries** — new content, authored separately,
   tagged by Intent and Audience for retrieval. Candidate sources for
   Phase 1: the canonical repository's own Informative-status material
   (`Examples/`, `Adoption/`, ADR rationale in `Governance/ADR-Candidates.md`)
   already carries exactly this kind of non-normative, explanatory
   content and could be indexed as a starting corpus, alongside new
   content authored specifically for comparison/persuasion/teaching that
   has no home in either repository today. **Open question for the
   Architect** — see below.

Every item drawn from source (2) carries a `kind: "expert-knowledge"`
tag, kept structurally distinct from `kind: "specification-evidence"`
items from source (1), all the way through to Answer Composition. This
is the same "no answer without Evidence" discipline restated at this
layer (per `Architecture-Status-v0.1.md`), extended with an explicit
normative/non-normative distinction that did not previously need to
exist.

## Intent and Audience — Two Independent Dimensions

Modeled as two separate, orthogonal classifications, never fused into
one taxonomy.

```python
class Intent(str, Enum):
    EXPLAIN = "explain"
    COMPARE = "compare"
    DEFEND = "defend"
    TEACH = "teach"
    ADVISE = "advise"

class Audience(str, Enum):
    DEVELOPER = "developer"
    ARCHITECT = "architect"
    PRODUCT_MANAGER = "product_manager"
    OPERATIONS = "operations"
    CEO_FOUNDER = "ceo_founder"
    INVESTOR = "investor"
```

`Intent Analysis` and `Audience Analysis` are separate pipeline stages,
each producing its own result:

```python
class IntentAnalysisResult(BaseModel):
    primary: Intent
    secondary: Optional[Intent] = None

class AudienceAnalysisResult(BaseModel):
    audiences: list[tuple[Audience, float]]  # ranked, supports blending
```

Audience supports blending (e.g. CTO+COO both detected, each weighted) —
this is the mechanism the Phase 1 mission's "blend automatically for
mixed audiences" requirement maps to. Intent carries an optional
secondary value rather than a weighted list, since the mission's own
examples of blending were audience mixes, not intent mixes.

Both stages operate **only on the Question text** (and the static
Intent/Audience definitions). Neither has a handle to Knowledge
Selection, the Expert Knowledge Base, Retrieval, or the Registry —
structurally, not by convention, the same discipline M019 established
for the LLM layer.

Classification itself follows the pattern this codebase has now proven
twice (`FilesystemDocumentationNormalizer`/`LLMDocumentNormalizer`;
`LLMAdapter` as an optional presentation swap-in): a deterministic
rule/keyword-based classifier is the Phase 1 default, with an
LLM-based classifier available as an opt-in alternative via the
Interaction Layer. Neither implementation changes the
`IntentAnalysisResult`/`AudienceAnalysisResult` shape.

## Knowledge Selection

Given `IntentAnalysisResult` + `AudienceAnalysisResult`, queries both
sources described above and returns a tagged, provenance-labeled set:

```python
class KnowledgeItem(BaseModel):
    kind: Literal["specification-evidence", "expert-knowledge"]
    content: str
    source_reference: str
    audience_tags: list[Audience] = []
    intent_tags: list[Intent] = []

class KnowledgeSelection(BaseModel):
    specification_evidence: list[KnowledgeItem]
    expert_knowledge: list[KnowledgeItem]
```

Selection is deterministic tag/filter matching in Phase 1, consistent
with this repository's deterministic-first philosophy — not LLM-ranked.
An LLM-assisted matcher is a plausible future swap-in, not part of this
milestone.

## Expert Reasoning

Combines the two `KnowledgeSelection` lists into a structure shaped by
the detected Intent (e.g. Explain → definition + example; Compare →
OCOM's position + alternative + tradeoffs; Defend → problem framing +
OCOM's answer; Teach → progressive explanation + analogy; Advise →
recommendation framed for the audience's own decision context) and
Audience (register/vocabulary). Output is still structured data, not
prose — mirroring how `ComposedAnswer` already separates structured
composition from text generation.

```python
class ExpertReasoningResult(BaseModel):
    intent: IntentAnalysisResult
    audiences: AudienceAnalysisResult
    grounded_points: list[KnowledgeItem]        # kind == specification-evidence
    explanatory_points: list[KnowledgeItem]      # kind == expert-knowledge
    reasoning_structure: str                      # which shape was applied, for traceability
```

**Explicit boundary, restated from the M019 discipline and sharpened
here:** any claim drawn from `expert_knowledge` — comparisons,
persuasive framing, "why you need this" arguments — must remain tagged
as non-normative opinion/analysis through to final output. It is never
presented with the same certainty as a `specification-evidence` claim.
This is a distinct discipline from "must not invent facts" (M019); it
is "must not blur sourced opinion with grounded fact."

## Answer Composition

Produces an `ExpertComposedAnswer`, the Expert-layer analogue of today's
`ComposedAnswer`:

```python
class ExpertComposedAnswer(BaseModel):
    question: str
    intent: IntentAnalysisResult
    audiences: AudienceAnalysisResult
    grounded_points: list[KnowledgeItem]
    explanatory_points: list[KnowledgeItem]
    reasoning_structure: str
```

This is the object handed to the Interaction Layer — structurally
parallel to how `ComposedAnswer` is handed to today's `LLMAdapter`.

## Interaction Layer (renamed from "LLM Presentation")

Renamed because, after this milestone, the LLM (where used) is no
longer a pure last-mile formatter — it may also assist Intent/Audience
classification, a genuinely different responsibility. "Interaction
Layer" names the role without committing to a single implementation, so
either half can later be swapped for rules or a specialized model
without a further rename.

Two invocation points, each inheriting the M019 discipline independently:

1. **Front — classification assist.** Optional LLM-backed alternative
   to the deterministic Intent/Audience classifiers. Operates only on
   the Question text. No handle to Knowledge Selection, the Expert
   Knowledge Base, Retrieval, or the Registry — structurally incapable
   of influencing what gets selected beyond the classification result
   itself.
2. **Back — final phrasing.** Takes the completed `ExpertComposedAnswer`
   and produces natural-language text, exactly as `LLMAdapter.enhance()`
   does today for `ComposedAnswer`: additive only, never mutates its
   input, never retrieves/ranks/invents, never a required dependency,
   always falls back gracefully.

Both invocation points are optional and independently swappable. Phase
1 ships with deterministic defaults for both; wiring either to a real
LLM provider is additive, not a redesign, matching the two proven
precedents (Normalizer, LLMAdapter).

## Explicitly Deferred

- **Comprehension Detection** — tracking what a specific listener
  already understands across a conversation. Requires user modeling,
  conversation memory, and adaptive learning — substantially larger
  than the rest of this milestone combined. Not started here.
- **Company Intelligence** — per-organization modeling, terminology
  learning, and adoption support. Follows Phase 1 per the OCOM Expert
  mission, not part of it.

## Open Questions for the Architect

- Where does Expert Knowledge Base content live — a new directory in
  this repository, a separate content repository, or indexed directly
  from the canonical Specification's existing Informative-status docs
  (`Examples/`, `Adoption/`, ADR rationale)? This design assumes at
  least the latter as a Phase 1 starting corpus but does not decide the
  authoring/storage model for net-new comparison/rationale content.
- Should the Intent and Audience enums be treated as closed for Phase 1,
  or explicitly extensible (as OCOM's own Relationship Types are)?
- Does Knowledge Selection's deterministic tag-matching need a minimum
  coverage guarantee (e.g. every Specification concept has at least one
  tagged Expert Knowledge entry per Audience), or is partial coverage
  acceptable for Phase 1 with graceful degradation?

## Test Plan (design-level)

- Intent/Audience classifiers: deterministic keyword-based fixtures per
  Intent/Audience value, including a blended-audience case.
- Knowledge Selection: returns correctly tagged/provenance-labeled
  items from both sources; never fabricates a `specification-evidence`
  item not backed by the existing Retrieval/Registry pipeline.
- Expert Reasoning: `explanatory_points` never leak into
  `grounded_points` and vice versa; reasoning structure matches the
  detected Intent.
- Answer Composition: deterministic given a fixed Question, Intent, and
  Audience — same repeatability discipline as `ComposedAnswer`.
- Interaction Layer: both invocation points follow the M019 test
  pattern — fallback-never-raises, never mutates input, byte-identical
  deterministic output when disabled.

## Roadmap

```
✅ M001-M018 — OCOM Reader MVP + Repository Independence + Retrieval Evolution + Extensibility + Web UI (frozen)
✅ M019 — Optional LLM Layer (frozen)
⬜ M020 — OCOM Expert Phase 1: Intent, Audience, Expert Knowledge — this document (design only)
```
