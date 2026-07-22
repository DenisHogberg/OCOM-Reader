"""Working model of Evidence.

Grounded in the OCOM Memory Specification: Memory/Memory Record.md.docx
states that a Memory Record "may reference one or more Evidence
Records" and that "Evidence provides the basis for explainability and
confidence assessment", with the full structure deferred to a separate
Evidence Overlay specification (Memory/Evidence Overlay.md.docx —
itself still an early draft at the time this was written).

This is a Phase 1 placeholder, not that future Evidence Overlay. It
exists to reserve the right architectural place for provenance now,
rather than let it hide inside `metadata`:

- `metadata` describes the object itself (descriptive/administrative/
  technical attributes — see Meta/Metadata.md.docx).
- `evidence` describes why we believe the object's data is what it is,
  and where it was obtained from. That is a fundamentally different
  kind of information and must not be collapsed into the former.

No confidence scoring, no verification workflow, no Evidence storage
of its own yet — those belong to the real Memory/Confidence Model and
Write-back Governance specs, out of scope for the Reader today.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Evidence(BaseModel):
    """A single piece of provenance supporting an OCOMObject."""

    identity: str
    source: str
    reference: str
    captured_at: datetime
    excerpt: Optional[str] = None
