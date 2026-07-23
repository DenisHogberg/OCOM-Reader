"""Query — the user's question, nothing more.

No LLM, no parsing, no intent extraction. Understanding what the
question means is entirely the next layer's job (ObjectRegistry's
candidate search, which in v0.1 is plain keyword overlap — see
registry.py). Query only carries what the user actually typed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Query(BaseModel):
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
