"""OpenAI provider — the `openai` SDK is imported inside `__init__`
only, never at module load time, so `import ocom_reader.llm` never
fails even when the SDK isn't installed (it isn't, in this
environment — confirmed directly, not assumed). API key is read from
`OPENAI_API_KEY` only — never a constructor argument, never persisted.
"""

from __future__ import annotations

import os
from typing import Optional

from ocom_reader.llm.exceptions import LLMProviderUnavailableError
from ocom_reader.llm.models import LLMConfig

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider:
    def __init__(self, config: LLMConfig) -> None:
        try:
            import openai
        except ImportError as exc:
            raise LLMProviderUnavailableError(
                "The 'openai' package is not installed. Install it with: pip install ocom-reader[openai]"
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMProviderUnavailableError("OPENAI_API_KEY is not set.")

        self._client = openai.OpenAI(api_key=api_key)
        self._model = config.model or DEFAULT_MODEL

    def generate(self, prompt: str, *, timeout: float) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return response.choices[0].message.content
