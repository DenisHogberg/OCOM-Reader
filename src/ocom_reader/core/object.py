"""Working model of an OCOM Object.

This is a Phase 1 engineering model, not the official OCOM specification.
Field selection follows the Core Characteristics defined in
Meta/Object.md.docx (Identity, Metadata, Classification, Relationships,
Lifecycle, Ownership, Governance). Optional characteristics (Evaluation,
Versioning, Capabilities, Policies, Contracts, Constraints) are
intentionally omitted until a real use case needs them.

The object carries no field that encodes where it came from as part of
its identity or schema shape — source adapters are external to the
object and must not shape it. But provenance itself (which source
produced this data, what was captured, when) is a first-class concept,
not incidental metadata: it is tracked via `evidence`
(see core/evidence.py), kept structurally separate from `metadata`.
`metadata` describes the object; `evidence` explains where its data
came from.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ocom_reader.core.evidence import Evidence


class Relationship(BaseModel):
    """An explicit, named association to another OCOM Object."""

    target_id: str
    relationship_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCOMObject(BaseModel):
    """Source-agnostic representation of any managed element."""

    identity: str
    object_type: str

    metadata: dict[str, Any] = Field(default_factory=dict)
    classification: list[str] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    lifecycle_state: Optional[str] = None
    owner: Optional[str] = None
    governance: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
