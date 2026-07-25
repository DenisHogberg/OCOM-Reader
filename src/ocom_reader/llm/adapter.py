"""LLMAdapter — the one thing anything outside `llm/` ever calls.

Imports `ComposedAnswer` from `composer.models` — a plain data model,
not `AnswerComposer`/`RetrievalEngine`/`KnowledgeRegistry`/`Indexer`
themselves (never imported here, verified via `git diff --stat` and a
grep at the end of MILESTONE-019.md, the same check M017 ran for
`plugins/`). `enhance()` never raises — every failure mode becomes an
`LLMResult` with `fallback_reason` set, never an exception the caller
must catch. This is what "failures must never interrupt the normal
Reader pipeline" means structurally.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Optional

from ocom_reader.composer.models import ComposedAnswer
from ocom_reader.llm.exceptions import LLMProviderUnavailableError
from ocom_reader.llm.models import LLMConfig, LLMProviderName, LLMResult
from ocom_reader.llm.protocol import LLMProvider

SYSTEM_INSTRUCTION = (
    "You are formatting an already-researched answer for a documentation reader. "
    "You may rewrite, summarize, adapt tone, explain terminology, and format as Markdown. "
    "You must not invent facts, citations, or documents beyond what is given below. "
    "The evidence and reading order are already final and must not be reordered or replaced."
)


class LLMAdapter:
    def __init__(self, config: LLMConfig, provider: Optional[LLMProvider] = None) -> None:
        self._config = config
        self._unavailable_reason: Optional[str] = None
        self._provider = provider if provider is not None else self._build_provider(config)

    def enhance(self, answer: ComposedAnswer) -> LLMResult:
        if self._config.provider == LLMProviderName.DISABLED:
            return LLMResult(text=None, used_provider=LLMProviderName.DISABLED)

        if self._provider is None:
            return LLMResult(
                text=None,
                used_provider=self._config.provider,
                fallback_reason=self._unavailable_reason or "provider unavailable",
            )

        prompt = self._build_prompt(answer)
        # Deliberately not a `with ThreadPoolExecutor(...) as pool:` block —
        # its __exit__ calls shutdown(wait=True), which blocks until the
        # still-running background thread finishes, silently defeating the
        # timeout below (a real bug caught during this milestone's own
        # verification: a 0.2s-timeout call actually took 2s end to end).
        # shutdown(wait=False) lets enhance() return immediately; the
        # orphaned thread finishes in the background on its own — Python
        # has no way to forcibly kill a running thread, an honest
        # limitation named in MILESTONE-019.md, not hidden.
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(self._provider.generate, prompt, timeout=self._config.timeout_seconds)
            text = future.result(timeout=self._config.timeout_seconds)
            return LLMResult(text=text, used_provider=self._config.provider)
        except FuturesTimeoutError:
            return LLMResult(text=None, used_provider=self._config.provider, fallback_reason="timeout")
        except Exception as exc:  # provider/network/API error of any kind — never propagate
            return LLMResult(text=None, used_provider=self._config.provider, fallback_reason=str(exc))
        finally:
            pool.shutdown(wait=False)

    def _build_provider(self, config: LLMConfig) -> Optional[LLMProvider]:
        try:
            if config.provider == LLMProviderName.OPENAI:
                from ocom_reader.llm.providers.openai import OpenAIProvider

                return OpenAIProvider(config)
            if config.provider == LLMProviderName.ANTHROPIC:
                from ocom_reader.llm.providers.anthropic import AnthropicProvider

                return AnthropicProvider(config)
        except LLMProviderUnavailableError as exc:
            self._unavailable_reason = str(exc)
        return None

    def _build_prompt(self, answer: ComposedAnswer) -> str:
        lines = [SYSTEM_INSTRUCTION, "", f"Question: {answer.query}", "", f"Answer: {answer.answer}", ""]

        lines.append("Evidence:")
        for doc in answer.evidence:
            lines.append(f"- {doc.document.title} ({doc.document.path}): {'; '.join(doc.reasons)}")

        if answer.related_documents:
            lines.append("")
            lines.append("Related documents:")
            for doc in answer.related_documents:
                lines.append(f"- {doc.document.title} ({doc.document.path})")

        if answer.reading_order:
            lines.append("")
            lines.append("Recommended reading order:")
            for i, doc in enumerate(answer.reading_order, start=1):
                lines.append(f"{i}. {doc.title} ({doc.path})")

        return "\n".join(lines)
