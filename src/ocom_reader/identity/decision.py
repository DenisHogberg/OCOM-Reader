"""IdentityDecision — the result of comparing two OCOMObjects.

Minimal experimental model per
docs/architecture/OCOM-Identity-Resolution-v0.1.md §2, scaled down for
this validation experiment (no ResolutionRequest/context wrapper yet —
that is only worth building once this decision model has been tried
against real data).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class IdentityDecision(BaseModel):
    result: Literal["MATCH", "NEW", "UNCERTAIN"]
    confidence: str
    reasoning: str
    matched_object_id: Optional[str] = None
