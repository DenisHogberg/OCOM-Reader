"""Retrieval data models.

No generated text anywhere in this module — every field is a pointer,
a fixed-vocabulary label, or a number. `MatchReason.detail` records a
fact (which token matched, or which entry a relation came from), never
composed prose. Formatting reasons into a readable string is
`RetrievalEngine.explain()`'s job at presentation time, not something
stored here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ocom_reader.registry.models import RegistryEntry


class QueryObject(BaseModel):
    raw: str
    tokens: list[str] = Field(default_factory=list)


class MatchReason(BaseModel):
    kind: str  # "title_match" | "heading_match" | "preview_match" | "builds_on" | "references" | "architecture_sequence"
    detail: str  # the matched token, or the registry_id this relation came from


class RetrievalMatch(BaseModel):
    entry: RegistryEntry
    reasons: list[MatchReason] = Field(default_factory=list)
    score: float = 0.0
    related: list[str] = Field(default_factory=list)  # registry_ids of directly connected entries


class RetrievalResult(BaseModel):
    query: QueryObject
    matches: list[RetrievalMatch] = Field(default_factory=list)
