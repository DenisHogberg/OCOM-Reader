"""ResolutionPolicy v0.1 — folds N pairwise identity comparisons into one outcome.

Implements docs/architecture/OCOM-Runtime-v0.2-Resolution-Evidence-Design.md
§3-5's Merge Safety Rules:

  1. Merge requires exactly one MATCH among all candidates. Zero -> NEW
     (or UNCERTAIN if any UNCERTAIN exists). More than one -> UNCERTAIN.
  2. A MATCH's validity does not depend on the absence of unrelated
     UNCERTAIN results elsewhere (Case C) — but every UNCERTAIN is
     recorded as a warning, never silently dropped.
  3. No decision is applied without a recorded reason.

This component receives only the *results* of comparisons already
made elsewhere (by IdentityResolver, against Storage) — it does not
look anything up, call Storage, or touch IdentityResolver/OCOMObject
itself. It is a pure fold: list of ResolutionCandidate in, one
ResolutionOutcome out. Deliberately decoupled from
`identity.decision.IdentityDecision` (no import from `identity/`) so
this stays a standalone, independently-testable unit, the same way
`runtime/query/` and `runtime/search/` do not depend on `identity/`
either — a future integration task maps IdentityDecision instances to
ResolutionCandidate, not this module.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ResolutionCandidate(BaseModel):
    object_id: str
    decision: Literal["MATCH", "UNCERTAIN", "NEW"]
    confidence: str


class ResolutionOutcome(BaseModel):
    result: Literal["ACCEPT", "UNCERTAIN", "NEW"]
    accepted_object_id: Optional[str] = None
    reason: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class ResolutionPolicy:
    def decide(self, candidates: list[ResolutionCandidate]) -> ResolutionOutcome:
        matches = [c for c in candidates if c.decision == "MATCH"]
        uncertains = [c for c in candidates if c.decision == "UNCERTAIN"]

        if len(matches) == 1:
            warnings = ["uncertain_candidate_present"] if uncertains else []
            return ResolutionOutcome(
                result="ACCEPT",
                accepted_object_id=matches[0].object_id,
                warnings=warnings,
            )

        if len(matches) > 1:
            return ResolutionOutcome(result="UNCERTAIN", reason="multiple_matches")

        if uncertains:
            return ResolutionOutcome(result="UNCERTAIN", reason="ambiguous_candidates")

        return ResolutionOutcome(result="NEW")
