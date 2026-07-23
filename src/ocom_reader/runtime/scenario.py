"""Full v0.2 query-time scenario — minimal new glue, no existing layer touched.

Wires QueryNormalizer -> Registry -> IdentityResolver -> ResolutionPolicy
-> EvidenceAggregator -> EvidencePresentationMapper -> AnswerComposer for
answering a query, reconciling ambiguity before ever composing an
answer. `runtime/pipeline.py`'s `ask()` is untouched — it still does
the simple "aggregate everything Registry found" thing it always has.
This module is the version that actually applies
docs/architecture/OCOM-Runtime-v0.2-Resolution-Evidence-Design.md
end to end.

Query-time identity resolution among search results was named as an
open, undecided question in OCOM-Identity-Resolution-v0.1.md §7 and
MILESTONE-002 ("closer to clustering than a single yes/no check") —
this module makes one concrete, minimal choice to make the full
scenario testable, not a general clustering algorithm: the first
candidate Registry returns is the anchor; every other candidate is
compared against it, pairwise, exactly like ingestion-time comparison.
See the regression test's findings for what this doesn't solve
(three or more mutually-ambiguous candidates, for one).
"""

from __future__ import annotations

from dataclasses import dataclass

from ocom_reader.agent.answer import NOT_GROUNDED_TEXT, Answer
from ocom_reader.agent.query import Query
from ocom_reader.identity.resolver import IdentityResolver
from ocom_reader.runtime.context import RuntimeContext
from ocom_reader.runtime.evidence.mapper import EvidencePresentationMapper
from ocom_reader.runtime.resolution.policy import ResolutionCandidate, ResolutionOutcome, ResolutionPolicy

AMBIGUOUS_TEXT = "Multiple plausible matches were found; cannot answer confidently."


@dataclass
class ResolvedAnswer:
    resolution: ResolutionOutcome
    answer: Answer


def ask_with_resolution(query_text: str, ctx: RuntimeContext) -> ResolvedAnswer:
    candidates = ctx.registry.find_candidates(Query(text=query_text))

    if not candidates:
        return ResolvedAnswer(
            resolution=ResolutionOutcome(result="NEW"),
            answer=Answer(text=NOT_GROUNDED_TEXT, sources=[], grounded=False),
        )

    if len(candidates) == 1:
        outcome = ResolutionOutcome(result="ACCEPT", accepted_object_id=candidates[0].identity)
        resolved_objects = candidates
    else:
        anchor = candidates[0]
        resolver = IdentityResolver()
        resolution_candidates = []
        for other in candidates[1:]:
            decision = resolver.resolve(anchor, other)
            resolution_candidates.append(
                ResolutionCandidate(
                    object_id=other.identity,
                    decision=decision.result,
                    confidence=decision.confidence,
                )
            )
        outcome = ResolutionPolicy().decide(resolution_candidates)

        if outcome.result == "UNCERTAIN":
            # No merge, and — just as important — no aggregating the
            # ambiguous objects' Evidence together into one misleading
            # answer either. Refuse, the same way "no Evidence at all"
            # is refused.
            return ResolvedAnswer(
                resolution=outcome,
                answer=Answer(text=AMBIGUOUS_TEXT, sources=[], grounded=False),
            )

        # ACCEPT or NEW: only the anchor is safe to answer from — the
        # other candidates were not confirmed to be the same object.
        resolved_objects = [anchor]

    context = ctx.evidence_aggregator.aggregate(resolved_objects)
    answer = ctx.answer_composer.compose(context)

    # Evidence Presentation: sources are re-expressed through the
    # mapper so an internal pointer like
    # "object-intelligence:classification-engine"'s reference chain
    # never reaches the caller as-is. Note: AnswerComposer's `.text`
    # is still built from raw Evidence inside `agent/answer.py`
    # (frozen for this task) and is NOT re-rendered here — see the
    # regression test's findings for why that remains a known gap.
    mapper = EvidencePresentationMapper()
    human_sources = [mapper.to_view(evidence).reference for evidence in context.evidence]
    answer = answer.model_copy(update={"sources": human_sources})

    return ResolvedAnswer(resolution=outcome, answer=answer)
