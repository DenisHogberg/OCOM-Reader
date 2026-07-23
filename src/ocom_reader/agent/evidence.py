"""EvidenceAggregator — collect Evidence from candidate OCOMObjects.

v0.1 aggregates evidence across every candidate ObjectRegistry found,
not just one "resolved" object — there is no Identity Resolver in this
slice to guarantee a single correct object, so the honest result is a
Unified Evidence Context built from whatever was actually found, not a
false claim of precision. See docs/architecture/OCOM-Agent-v0.1-Design.md
§6-7 for the full Identity Resolution design this intentionally does
not implement yet.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject


class UnifiedEvidenceContext(BaseModel):
    objects: list[OCOMObject] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class EvidenceAggregator:
    def aggregate(self, objects: list[OCOMObject]) -> UnifiedEvidenceContext:
        evidence: list[Evidence] = []
        for obj in objects:
            evidence.extend(obj.evidence)
        return UnifiedEvidenceContext(objects=objects, evidence=evidence)
