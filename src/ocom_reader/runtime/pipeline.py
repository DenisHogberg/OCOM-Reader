"""Runtime pipeline — coordinates existing components into one flow:

    Document -> Adapter -> Normalizer -> OCOMObject
             -> ClassificationEngine -> IdentityResolver -> Storage
             -> (query time) Registry -> EvidenceAggregator -> AnswerComposer

This module makes no classification decision, no identity decision, and
no grounding decision — every one of those comes from an existing,
independently-tested component (`ClassificationEngine`,
`IdentityResolver`, `AnswerComposer`). What this module owns is strictly
orchestration:

- what order components run in;
- what to do with one component's output before handing it to the next
  (e.g. calling `apply_classification()` to actually attach a proposal,
  since `ClassificationEngine.classify()` only proposes);
- how to turn `IdentityResolver`'s pairwise-only comparison into a
  decision against a whole `Storage`, since nothing else in this
  codebase does that yet.

That last point is a real, new piece of coordination logic (see
`_resolve_against_storage`), not a hidden intelligence component: it
never itself decides MATCH/NEW/UNCERTAIN — it only decides *which
pairs* `IdentityResolver` compares and how to fold N pairwise decisions
into the one decision this pipeline needs to act on. See
docs/architecture/MILESTONE-004.md for why this fold strategy
(first MATCH wins, else first UNCERTAIN wins, else NEW) is flagged as a
new assumption, not a settled design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ocom_reader.agent.answer import Answer
from ocom_reader.agent.query import Query
from ocom_reader.core.object import OCOMObject
from ocom_reader.identity.decision import IdentityDecision
from ocom_reader.interfaces.normalizer import Normalizer
from ocom_reader.intelligence.classification import apply_classification
from ocom_reader.runtime.context import RuntimeContext


@dataclass
class IngestionResult:
    decision: IdentityDecision
    stored: OCOMObject


def ingest_document(raw: Any, normalizer: Normalizer, ctx: RuntimeContext) -> IngestionResult:
    """Document -> Adapter output (raw) -> Normalizer -> Classification -> Identity -> Storage.

    The Adapter itself is not called here — callers already have `raw`
    from iterating `Adapter.fetch()`, unchanged, exactly as every prior
    phase of this project has done. This function starts at Normalizer.
    """
    candidate = normalizer.normalize(raw)

    proposal = ctx.classification_engine.classify(candidate)
    candidate = apply_classification(candidate, proposal)  # no-op if proposal.is_empty

    decision, matched = _resolve_against_storage(candidate, ctx)

    if decision.result == "MATCH" and matched is not None:
        # Append-only merge: existing Evidence is never edited or
        # dropped, only added to. Same pattern already validated in
        # tests/test_llm_normalizer_same_object_recognition.py.
        merged = matched.model_copy(update={"evidence": matched.evidence + candidate.evidence})
        ctx.storage.save(merged)
        return IngestionResult(decision=decision, stored=merged)

    # NEW, or UNCERTAIN: never merge automatically. The candidate is
    # persisted under its own identity so nothing is lost — a
    # duplicate is cheap to reconcile later; a wrong merge is not
    # (same asymmetry as docs/architecture/OCOM-Identity-Resolution-v0.1.md §5).
    ctx.storage.save(candidate)
    return IngestionResult(decision=decision, stored=candidate)


def _resolve_against_storage(
    candidate: OCOMObject, ctx: RuntimeContext
) -> tuple[IdentityDecision, Optional[OCOMObject]]:
    """Compare `candidate` against every stored object of the same
    object_type, pairwise, via the unmodified IdentityResolver, and
    fold the results into one decision: first MATCH wins; else first
    UNCERTAIN wins; else NEW. IdentityResolver itself never sees more
    than two objects at a time and makes no folding decision — that
    logic lives here because nothing else in this codebase does it yet.
    """
    existing_of_type = [o for o in ctx.storage.list() if o.object_type == candidate.object_type]
    if not existing_of_type:
        return (
            IdentityDecision(
                result="NEW",
                confidence="Verified",
                reasoning="no existing objects of this object_type in storage to compare against",
            ),
            None,
        )

    decisions = [(ctx.identity_resolver.resolve(candidate, existing), existing) for existing in existing_of_type]

    for decision, existing in decisions:
        if decision.result == "MATCH":
            return decision, existing

    for decision, existing in decisions:
        if decision.result == "UNCERTAIN":
            return decision, existing

    return decisions[0]


def ask(query_text: str, ctx: RuntimeContext) -> Answer:
    """Query -> Registry -> EvidenceAggregator -> AnswerComposer, unchanged."""
    candidates = ctx.registry.find_candidates(Query(text=query_text))
    context = ctx.evidence_aggregator.aggregate(candidates)
    return ctx.answer_composer.compose(context)
