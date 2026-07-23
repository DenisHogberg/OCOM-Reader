"""NormalizedQuery — the output of QueryNormalizer.

The value this whole layer exists to produce, per
docs/architecture/OCOM-Runtime-v0.2-Reliability-Design.md §3: a query's
original text next to its cleaned token list. Nothing else — no score,
no interpretation, no identity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedQuery(BaseModel):
    raw: str
    tokens: list[str] = Field(default_factory=list)
