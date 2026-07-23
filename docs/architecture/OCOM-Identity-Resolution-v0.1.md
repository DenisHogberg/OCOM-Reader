# OCOM Identity Resolution v0.1 — Design

**Status:** Draft — partially implemented. See "Implementation Status" below: the decision model (§3, Option B) and evidence-gating rule (§4) were built; the batch `ResolutionRequest`/`ResolutionContext` contract (§2) was not.
**Date:** 2026-07-23
**Builds on:** [OCOM Agent v0.1 Design](OCOM-Agent-v0.1-Design.md) §6-7, [ADR-002](ADR-002-agent-vertical-slice-boundaries.md), [MILESTONE-002](MILESTONE-002.md)
**Core contracts this design does not touch:** `core/object.py`, `core/evidence.py`, `interfaces/`, `storage/`, and everything already implemented under `agent/` (`query.py`, `registry.py`, `evidence.py`, `answer.py`). This is a contract for a component that does not exist yet.

This document answers one question, and only one:

> Given a set of candidate `OCOMObject`s, do any of them represent the
> same real-world object as each other, or as something already known?

It does not decide how that answer gets used. What happens after a
decision — merging evidence, registering a new object, refusing to
answer — belongs to `Registry`, `EvidenceAggregator`, and
`AnswerComposer` respectively, all of which already exist and are
untouched by this design.

## Implementation Status (added by [Architecture Consistency Cleanup v0.1](Architecture-Status-v0.1.md))

A follow-up task ("IdentityResolver v0.1 — Validation Experiment")
implemented a deliberately scaled-down version of this contract one
step after this document was written, and said so at the time in its
own code — this section makes that explicit here too, since later
documents (ADR-005, ADR-006, the Classification Engine and Enrichment
Provenance designs) all build on "IdentityResolver" without repeating
that caveat.

**Implemented, in `identity/resolver.py` and `identity/decision.py`:**

- The **decision model**: §3's Option B (rule-based similarity —
  `object_type` hard gate, weighted word-overlap over
  `metadata["identity"]` and `classification`, fixed thresholds).
  Realized with a slightly different formula than the `difflib`
  sketch in §3 (Jaccard word-overlap, not `SequenceMatcher`), but the
  same option, same reasoning, same v0.1 scope.
- The **evidence-gating rule** (§4): `MATCH` is refused when either
  side has no `Evidence`, downgrading to `UNCERTAIN`.
- The **three-outcome model**: `MATCH` / `NEW` / `UNCERTAIN`, matching
  §2's design intent that `UNCERTAIN` be first-class, not bolted on.
- **Statelessness** (§6): no constructor dependency on `Storage` or
  `Registry` — confirmed, `IdentityResolver` takes only the two
  objects being compared.

**Remains conceptual design only, not implemented:**

- The **`ResolutionRequest`/`ResolutionContext` batch contract** (§2).
  The real `IdentityResolver.resolve()` takes exactly two `OCOMObject`s
  (`candidate`, `existing`) and returns one `IdentityDecision` —
  pairwise, not `resolve(request) -> list[IdentityDecision]` over a
  `candidates`/`existing` batch.
- The fuller **`IdentityDecision` shape** from §2 —
  `candidate_identity`, `outcome`, `matched_identity`,
  `possible_matches`, `evidence_used` — was not built. The real
  `IdentityDecision` (`identity/decision.py`) has `result`,
  `confidence`, `reasoning`, `matched_object_id` only; there is no
  `possible_matches` list for the `UNCERTAIN` case and no
  `evidence_used` audit field.
- **§7's open question about where `IdentityResolver` gets called
  from** (inside `Registry.find_candidates()`, or as a separate step)
  is still open — the resolver has not been wired into `agent/` at
  all; every use of it today is direct, from tests.
- The **ingestion-time vs. query-time distinction** §2 built the
  `candidates`/`existing` split to serve is untested either way, for
  the same reason: nothing calls the resolver from a real pipeline
  yet.

None of this changes what §1–§7 argue *should* happen — the
responsibility boundary, the Option B decision, the evidence rule, and
the failure-mode reasoning all still describe what was actually built,
faithfully. What's listed above is the packaging (`ResolutionRequest`,
the richer `IdentityDecision`) that got simplified away during
implementation and never carried back into this document until now.

## 1. Responsibility

**In scope:**

- **Candidate comparison** — given two or more `OCOMObject`s, compare
  the fields available on them (`object_type`, `metadata`,
  `classification`, `evidence`) to assess whether they describe the
  same real-world thing.
- **Similarity evaluation** — apply a decision model (§3) to that
  comparison and produce a graded outcome, not just a boolean.
- **Identity decision** — emit a structured, auditable decision
  (§2) that names the outcome, the confidence behind it, and what was
  compared to reach it.

**Explicitly out of scope, and why each belongs elsewhere:**

- **Extraction** — turning raw data into an `OCOMObject` candidate in
  the first place is `Normalizer`'s job ([ADR-001](ADR-001-normalizer-architecture.md)).
  `IdentityResolver` never sees anything that isn't already a
  well-formed `OCOMObject`.
- **Storage** — `IdentityResolver` never calls `Storage.save()`,
  `Storage.delete()`, or anything else. It has no persistence of its
  own and no side effects at all — it is a pure function of its
  inputs. `Registry` decides what to do with a decision (register,
  merge, leave alone); `IdentityResolver` only decides what the
  decision *is*.
- **Answer generation** — composing a response to a user is
  `AnswerComposer`'s job. `IdentityResolver` produces no user-facing
  text.
- **Object creation** — even for a `"NEW"` outcome, `IdentityResolver`
  does not construct an `OCOMObject`. The candidate already exists
  (produced by `Normalizer`); `"NEW"` just means "treat the candidate
  as its own identity," nothing is built.
- **Core schema changes** — no field is added to `OCOMObject` or
  `Evidence` to support this design. Everything it needs
  (`metadata`, `classification`, `evidence`) already exists.
- **Writing to source systems** — `IdentityResolver` inherits the same
  boundary already stated for the whole Agent layer
  ([OCOM Agent v0.1 Design §8](OCOM-Agent-v0.1-Design.md#8-security-boundaries)):
  no dependency on `Adapter`, no access to any live source.
- **Replacing `Normalizer`** — `IdentityResolver` operates strictly
  downstream of it, on objects Normalizer has already produced,
  including their attached `Evidence`.

## 2. Input / Output Contract

```python
class ResolutionContext(BaseModel):
    trigger: Literal["ingestion", "query"]
    note: str | None = None   # e.g. the originating Query.text, for audit only —
                               # never used as a comparison signal itself

class ResolutionRequest(BaseModel):
    candidates: list[OCOMObject]   # object(s) whose identity is in question
    existing: list[OCOMObject]     # known objects to compare candidates against
    context: ResolutionContext

class IdentityDecision(BaseModel):
    candidate_identity: str            # which candidate this decision is about
    outcome: Literal["MATCH", "NEW", "UNCERTAIN"]
    matched_identity: str | None       # set only when outcome == "MATCH"
    possible_matches: list[str] = []   # set only when outcome == "UNCERTAIN"
    confidence: str                    # one of the OCOM Confidence levels — see §4
    reasoning: str                     # human-readable, for audit — never silent
    evidence_used: list[str]           # Evidence.reference values actually compared

class IdentityResolver:
    def resolve(self, request: ResolutionRequest) -> list[IdentityDecision]:
        """One decision per candidate, same order as request.candidates."""
```

Two things about this shape are deliberate:

- **The request carries `candidates` *and* `existing` separately**,
  even though both call sites end up passing `OCOMObject` lists,
  because the two callers mean different things by "candidate":
  - **Ingestion-time**: one fresh candidate from `Normalizer` vs. the
    `existing` objects `Registry.find_candidates()` already knows
    about. This is the scenario [§6 of the Agent Design doc](OCOM-Agent-v0.1-Design.md#6-identity-resolution-strategy)
    was written for.
  - **Query-time**: `Registry.find_candidates(query)` returns a list
    of keyword matches that may themselves contain duplicates of each
    other — there, `candidates` and `existing` may be the same list,
    and the resolver's job is closer to clustering than to a single
    yes/no check. [MILESTONE-002](MILESTONE-002.md) named this
    difference as untested; this contract is written to serve both
    without pretending they are identical, but which mode is used
    where remains open — see §7.
- **`UNCERTAIN` is a first-class outcome**, not a fallback. This
  resolves [Open Question 3](OCOM-Agent-v0.1-Design.md#10-open-questions)
  from the Agent Design doc ("does `IdentityDecision` need a third
  outcome for genuine ambiguity?") — yes, and this document defines it
  from the start rather than bolting it on after the fact.

## 3. Decision Model

Four options, evaluated rather than defaulted to the most capable one:

**Option A — Exact metadata matching.**
Compare `metadata["concept"]` (or another single designated field) for
literal string equality after case-folding. This is what
`LLMDocumentNormalizer`'s `_slugify` implicitly relies on today by
accident of producing the same string twice.
*Pros*: zero code, fully deterministic, trivially auditable.
*Cons*: already proven insufficient — [ADR-002](ADR-002-agent-vertical-slice-boundaries.md)
documents that even a punctuation mark (`"Object?"` vs `"Object"`)
breaks substring matching elsewhere in this codebase; exact-string
matching has the identical failure mode.

**Option B — Rule-based similarity.**
Normalize candidate fields (case-fold, strip punctuation, collapse
whitespace) and score similarity using a small set of explainable
signals: `object_type` equality as a hard gate, plus a string-distance
score (e.g. Python's stdlib `difflib.SequenceMatcher`, no new
dependency) over normalized `metadata` values and `classification`
overlap. Produces a numeric-ish score that maps to `MATCH` /
`UNCERTAIN` / `NEW` via fixed thresholds.
*Pros*: still zero new dependencies, still fully deterministic and
explainable (`reasoning` can name exactly which fields and score
produced the outcome), handles minor lexical variation (plurals,
punctuation, reordering) that Option A cannot.
*Cons*: still cannot recognize that two different-language
descriptions refer to the same concept — that is exactly the boundary
[Reasoning Consistency Test v0.1](MILESTONE-001.md) proved a
deterministic, non-interpretive approach cannot cross. This is a known,
accepted gap for v0.1 (§5, §6), not an oversight.

**Option C — LLM-assisted resolution.**
Reuse the `LLMClient` injection pattern already established in
`LLMDocumentNormalizer`: given a pair of candidates, ask a model
"do these describe the same real-world object?" with structured,
pydantic-validated output.
*Pros*: the only option that can plausibly close the exact gap Option
B leaves open (the bilingual case Reasoning Consistency Test v0.1
demonstrated).
*Cons*: cost, latency, non-determinism, and it reopens the exact
prompt-injection boundary already named in
[OCOM Agent v0.1 Design §8](OCOM-Agent-v0.1-Design.md#8-security-boundaries)
(`Evidence.excerpt` is external content and must be treated as data,
not instructions, by any prompt built from it). It also has no working
implementation to build on yet — `AnthropicLLMClient` has never been
exercised against a real API call in this project (MILESTONE-001).

**Option D — Hybrid.**
Run Option B first; only escalate to Option C when B's own outcome is
`UNCERTAIN` (i.e., some similarity signal fired, but not enough to
cross the `MATCH` threshold). This spends the expensive, non-deterministic
path only on cases the cheap path could not resolve either way.

**Decision for v0.1: Option B only. Option D is the named target
shape for a future version, not built now.**

Reasoning: Option A is already known to be insufficient (not a
hypothesis — a documented fact from this codebase's own history).
Option C, on its own or as D's escalation path, is not justified yet
because nothing has demonstrated Option B actually fails in a way that
matters for real usage — per [MILESTONE-002](MILESTONE-002.md)'s "what
experiments are needed next," that evidence doesn't exist yet. Building
the LLM escalation path before Option B has been tried against real
data would be the same mistake this project has repeatedly avoided:
adding a capability ahead of a proven need. §7 names the experiment
that would justify moving to D.

## 4. Evidence Requirements

**Can `IdentityResolver` decide without `Evidence`? Mechanically yes;
normatively, only toward the conservative outcomes.**

The comparison mechanism itself (Option B) operates on `object_type`,
`metadata`, and `classification` — none of which require `Evidence` to
be present. A candidate with an empty `evidence` list can still be
compared structurally.

But the *confidence* attached to a decision is a different claim, and
the OCOM Memory Specification is explicit about it:
Memory/Confidence.md.docx states **"Confidence shall not exist without
supporting evidence."** A `MATCH` decision is, in effect, a claim about
the reliability of merging two objects' provenance — that claim cannot
carry meaningful confidence if neither side has any `Evidence` backing
the fields being compared.

The rule this document adopts: **`IdentityResolver` must never emit
`MATCH` for a candidate whose `evidence` list is empty, or where none
of the compared fields are attributable to at least one `Evidence`
entry on either side.** In that situation the outcome is `UNCERTAIN`
(if the structural similarity score would otherwise have supported a
match) or `NEW` (if it would not). `evidence_used` in the output must
list the actual `Evidence.reference`s that justified the decision —
an empty `evidence_used` list is only valid alongside `outcome ==
"NEW"`.

This is deliberately asymmetric: **registering an object as `NEW`
without evidence is low-risk (it just means "not enough support to
merge," reversible later); deciding `MATCH` without evidence is
high-risk (it would silently blend two provenance trails on no
grounded basis)** — the same reversibility principle already applied
elsewhere in this project's operating discipline, now applied to
identity decisions specifically.

## 5. Failure Modes

- **Two objects are similar but not confidently the same.** Outcome is
  `UNCERTAIN`, never forced into `MATCH` or `NEW`. `possible_matches`
  records what was considered. The caller (`Registry`) is expected to
  leave both records separate rather than guess — `UNCERTAIN` is a
  valid, stable end state for v0.1, not a temporary error condition
  requiring resolution.
- **Confidence is low.** Confidence is not a label attached after an
  outcome is already chosen — it *gates* the outcome. A similarity
  score that would nominally cross the `MATCH` threshold is downgraded
  to `UNCERTAIN` if the resulting confidence would be below the
  `Low` tier described in Memory/Confidence.md.docx. `IdentityResolver`
  never emits `MATCH` at `Low` confidence.
- **Conflicting signals** (e.g. `object_type` differs but `metadata`
  values look identical, or vice versa). Never let one strong signal
  silently override a contradicting one. Outcome is `UNCERTAIN`, and
  `reasoning` must name the conflict explicitly (e.g. "object_type
  mismatch (Concept vs Document) despite metadata name match") rather
  than picking a side quietly.
- **An object was renamed.** This is the case v0.1 is honestly bad at:
  if a candidate's `metadata` values changed enough, Option B's
  string-distance score will likely fall below even the `UNCERTAIN`
  threshold, and the result will be `NEW` — a duplicate, not a
  correctly-tracked rename. This is an accepted, intentional failure
  mode, not a gap being hidden: **v0.1 is deliberately biased toward
  false negatives (missed matches, producing a duplicate `NEW` object)
  over false positives (an incorrect `MATCH` that blends unrelated
  evidence).** A duplicate is cheap to notice and merge later; a wrong
  merge corrupts a provenance trail in a way that is much harder to
  detect or undo. This bias is the same reasoning as §4's asymmetry,
  applied to a different failure mode.

## 6. v0.1 Scope

**Included:**

- `IdentityResolver.resolve()` implementing **Option B only**
  (§3): `object_type` equality as a hard gate, `difflib`-based string
  similarity over normalized `metadata`/`classification` fields,
  fixed (not configurable) thresholds mapping the score to `MATCH` /
  `UNCERTAIN` / `NEW`.
- The full `ResolutionRequest` / `IdentityDecision` contract from §2,
  including `UNCERTAIN` and the evidence-gating rule from §4, from the
  first implementation — not added later.
- Statelessness: no constructor dependency on `Storage` or `Registry`.
  Everything the resolver needs arrives via `ResolutionRequest`. This
  keeps it unit-testable with plain `OCOMObject` fixtures, the same way
  `AnswerComposer` is tested today — no `tmp_path`, no `Storage`
  required.

**Explicitly excluded from v0.1** (per this task's constraints, and
consistent with the project's standing discipline of not building
ahead of a proven need):

- Embeddings
- Vector database
- Graph database
- LLM-assisted resolution (Option C) and the Option D escalation path
  — designed and named above, not implemented until §7's experiment
  motivates it
- Configurable/tunable thresholds — fixed constants for now, revisited
  once real data exists to tune against
- Any invocation from `Registry` or `Query`-time code — this document
  defines the contract only; wiring `IdentityResolver` into
  `find_candidates()` or the ingestion path is a separate
  implementation task, not part of this design.

## 7. What This Design Does Not Decide

Carried forward honestly rather than papered over:

- Whether `ResolutionRequest`'s `candidates`/`existing` split actually
  serves the query-time clustering case as cleanly as the
  ingestion-time case (§2) — untested.
- Where `IdentityResolver` gets called from — inside
  `Registry.find_candidates()`, or as a step the caller applies
  afterward, as sketched in
  [§5.2 of the Agent Design doc](OCOM-Agent-v0.1-Design.md#52-query-time).
  Not decided here.
- The concrete similarity thresholds in Option B are unset in this
  document on purpose — picking numbers without data to validate them
  against would be a guess dressed up as a decision, exactly what this
  project's documentation discipline has consistently avoided.
