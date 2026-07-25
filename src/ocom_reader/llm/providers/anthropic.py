"""Anthropic provider — same isolation discipline as `openai.py`: the
`anthropic` SDK is imported inside `__init__` only. API key from
`ANTHROPIC_API_KEY` only.
"""

from __future__ import annotations

import os

from ocom_reader.llm.exceptions import LLMProviderUnavailableError
from ocom_reader.llm.models import LLMConfig

DEFAULT_MODEL = "claude-sonnet-5"


class AnthropicProvider:
    def __init__(self, config: LLMConfig) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMProviderUnavailableError(
                "The 'anthropic' package is not installed. Install it with: pip install ocom-reader[anthropic]"
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMProviderUnavailableError("ANTHROPIC_API_KEY is not set.")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = config.model or DEFAULT_MODEL

    def generate(self, prompt: str, *, timeout: float) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return response.content[0].text
