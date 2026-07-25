"""LLM configuration and result models. No field here ever holds a
secret: `LLMConfig` has no `api_key` — keys are read from environment
variables inside each provider only, never accepted as a constructor
argument, never persisted (this model is never written to `.ocom/`,
`workspace.json`, or anywhere else). See MILESTONE-019-DESIGN.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LLMProviderName(str, Enum):
    DISABLED = "disabled"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMConfig(BaseModel):
    provider: LLMProviderName = LLMProviderName.DISABLED
    model: Optional[str] = None
    timeout_seconds: float = 10.0


class LLMResult(BaseModel):
    text: Optional[str] = None
    used_provider: LLMProviderName
    fallback_reason: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.text is not None
