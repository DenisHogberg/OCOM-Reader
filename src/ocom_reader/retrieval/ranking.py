"""Ranker — deterministic scoring only, no probabilistic models.

A match's score is always the sum of fixed weights for its reasons —
SCORE_WEIGHTS below is the entire scoring "algorithm." Nothing here is
a coefficient tuned against data; each weight is a small, stated
integer reflecting relative confidence in a signal (a title match is
stronger evidence than a "references" relation), the same "fixed
table, not inference" discipline already used by
intelligence/classification.py and registry/registry_builder.py.

document_type is deliberately NOT used as a scoring factor — no
grounded weighting for "an ADR should outrank a README by how much"
exists yet, and inventing one without evidence would be exactly the
kind of unvalidated-threshold guess this project has repeatedly
avoided (e.g. ADR-005 leaving its own thresholds unset). Only
`entry.registry_id` is used, purely as a deterministic tie-breaker
when scores are equal — not a relevance judgment.
"""

from __future__ import annotations

from ocom_reader.retrieval.models import RetrievalMatch

SCORE_WEIGHTS: dict[str, float] = {
    "title_match": 10.0,
    "heading_match": 5.0,
    "preview_match": 2.0,
    "builds_on": 3.0,
    "architecture_sequence": 2.0,
    "references": 1.0,
}


class Ranker:
    def rank(self, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
        scored = [match.model_copy(update={"score": self._score(match)}) for match in matches]
        return sorted(scored, key=lambda m: (-m.score, m.entry.registry_id))

    def _score(self, match: RetrievalMatch) -> float:
        return sum(SCORE_WEIGHTS.get(reason.kind, 0.0) for reason in match.reasons)
