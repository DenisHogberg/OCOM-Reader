"""EvidenceView — the read-only, human-facing projection of an Evidence entry.

Never persisted, never written back onto the Evidence it was built
from. Carries `original_id` so the view always traces back to the real
`Evidence.identity` it came from — see mapper.py.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EvidenceView(BaseModel):
    source_type: str
    reference: str
    excerpt: Optional[str] = None
    original_id: str
