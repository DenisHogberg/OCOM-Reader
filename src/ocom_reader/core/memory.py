"""Memory Entry — the persisted, immutable form of any raw observation.

Per ADR-007 (Memory Before Knowledge): a Memory Entry is `RawDocument`,
promoted to a persisted stage, not a new concept invented independently.
Knowledge is always derived from Memory Entry, never the reverse, and a
Memory Entry is never derived from anything but the original observation
it records.

`id` is always a full SHA-256 content hash of `raw_content` — never
derived from source location, so identity survives a source being
moved, renamed, or re-platformed entirely (see ADR-007 §5).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ocom_reader.core.evidence import Evidence


def content_hash(raw_content: str) -> str:
    """Full SHA-256 hex digest of raw content. Never truncated: a Memory
    Entry's id is meant to be the durable, long-lived record, unlike
    OCOMObject.identity's shorter, per-domain hashes."""
    return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()


class MemoryEntry(BaseModel):
    """A persisted, immutable raw observation. See ADR-007."""

    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    source_identifier: str
    timestamp: datetime
    author: Optional[str] = None
    participants: list[str] = Field(default_factory=list)
    raw_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
