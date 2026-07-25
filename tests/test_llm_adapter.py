"""Optional LLM Layer (M019).

`LLMAdapter` is tested with an injected fake `LLMProvider` — the same
"prove the mechanism with a deterministic fake, no real API call"
discipline Phase 5's `LLMDocumentNormalizer` established. Provider
"unavailable" tests are real, not simulated: neither `openai` nor
`anthropic` is installed in this environment (confirmed directly), so
constructing either real provider genuinely raises
`LLMProviderUnavailableError` here.
"""

from __future__ import annotations

import time

import pytest

from ocom_reader.composer.models import ComposedAnswer, DocumentRef, ExplainedDocument
from ocom_reader.llm import LLMAdapter, LLMConfig, LLMProvider, LLMProviderName
from ocom_reader.llm.exceptions import LLMProviderUnavailableError


def _doc(registry_id: str, title: str) -> DocumentRef:
    return DocumentRef(
        registry_id=registry_id, document_id=registry_id, title=title, path=registry_id, document_type="ADR"
    )


def _answer(query: str = "runtime") -> ComposedAnswer:
    return ComposedAnswer(
        query=query,
        answer=f'Found 1 relevant document(s) for "{query}".',
        evidence=[
            ExplainedDocument(document=_doc("a.md", "Runtime"), reasons=["Title match: runtime"], score=10.0)
        ],
        related_documents=[
            ExplainedDocument(document=_doc("b.md", "Related Doc"), reasons=["Related via builds_on to a.md"], score=3.0)
        ],
        reading_order=[_doc("b.md", "Related Doc"), _doc("a.md", "Runtime")],
        grounded=True,
    )


class FakeProvider:
    def __init__(self, response: str = "Rewritten answer.") -> None:
        self.response = response
        self.received_prompt: str = ""

    def generate(self, prompt: str, *, timeout: float) -> str:
        self.received_prompt = prompt
        return self.response


class RaisingProvider:
    def generate(self, prompt: str, *, timeout: float) -> str:
        raise RuntimeError("simulated API error")


class SlowProvider:
    def __init__(self, delay: float) -> None:
        self.delay = delay

    def generate(self, prompt: str, *, timeout: float) -> str:
        time.sleep(self.delay)
        return "too slow"


# --- Protocol conformance ------------------------------------------------


def test_fake_provider_satisfies_the_protocol() -> None:
    assert isinstance(FakeProvider(), LLMProvider)


# --- Disabled (default) -----------------------------------------------------


def test_disabled_returns_no_text_and_no_fallback_reason() -> None:
    adapter = LLMAdapter(LLMConfig())  # provider defaults to DISABLED

    result = adapter.enhance(_answer())

    assert result.succeeded is False
    assert result.text is None
    assert result.fallback_reason is None
    assert result.used_provider == LLMProviderName.DISABLED


def test_default_config_is_disabled() -> None:
    assert LLMConfig().provider == LLMProviderName.DISABLED


# --- Success ----------------------------------------------------------------


def test_enhance_returns_the_provider_text_on_success() -> None:
    provider = FakeProvider("A friendly rewritten answer.")
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=provider)

    result = adapter.enhance(_answer())

    assert result.succeeded is True
    assert result.text == "A friendly rewritten answer."
    assert result.fallback_reason is None
    assert result.used_provider == LLMProviderName.OPENAI


# --- Prompt content is bounded to ComposedAnswer -----------------------


def test_prompt_contains_only_composed_answer_fields() -> None:
    provider = FakeProvider()
    answer = _answer(query="identity resolution")
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=provider)

    adapter.enhance(answer)

    prompt = provider.received_prompt
    assert "identity resolution" in prompt
    assert "Runtime" in prompt
    assert "a.md" in prompt
    assert "Related Doc" in prompt
    assert "Title match: runtime" in prompt


def test_prompt_instructs_the_model_not_to_invent_facts() -> None:
    provider = FakeProvider()
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=provider)

    adapter.enhance(_answer())

    assert "must not invent" in provider.received_prompt.lower()


# --- Failure paths never raise -----------------------------------------


def test_provider_raising_falls_back_gracefully() -> None:
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=RaisingProvider())

    result = adapter.enhance(_answer())  # must not raise

    assert result.succeeded is False
    assert "simulated API error" in result.fallback_reason


def test_timeout_falls_back_gracefully_and_does_not_block_the_caller() -> None:
    adapter = LLMAdapter(
        LLMConfig(provider=LLMProviderName.OPENAI, timeout_seconds=0.2), provider=SlowProvider(delay=2.0)
    )

    start = time.monotonic()
    result = adapter.enhance(_answer())
    elapsed = time.monotonic() - start

    assert result.succeeded is False
    assert result.fallback_reason == "timeout"
    assert elapsed < 1.0  # regression guard: must not block for the provider's full 2s delay


# --- Provider unavailable (real, not simulated, in this environment) -----


def test_openai_provider_unavailable_when_sdk_not_installed() -> None:
    from ocom_reader.llm.providers.openai import OpenAIProvider

    with pytest.raises(LLMProviderUnavailableError):
        OpenAIProvider(LLMConfig())


def test_anthropic_provider_unavailable_when_sdk_not_installed() -> None:
    from ocom_reader.llm.providers.anthropic import AnthropicProvider

    with pytest.raises(LLMProviderUnavailableError):
        AnthropicProvider(LLMConfig())


def test_adapter_falls_back_gracefully_when_openai_sdk_is_not_installed() -> None:
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI))  # no provider injected -> real construction path

    result = adapter.enhance(_answer())

    assert result.succeeded is False
    assert "not installed" in result.fallback_reason
    assert result.used_provider == LLMProviderName.OPENAI


def test_adapter_falls_back_gracefully_when_anthropic_sdk_is_not_installed() -> None:
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.ANTHROPIC))

    result = adapter.enhance(_answer())

    assert result.succeeded is False
    assert "not installed" in result.fallback_reason
    assert result.used_provider == LLMProviderName.ANTHROPIC


def test_openai_provider_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even if the SDK were installed, no API key must still be a clean
    LLMProviderUnavailableError, never an unhandled exception deeper in
    the SDK. Simulated by monkeypatching the import to succeed with a
    stand-in module, since the real SDK isn't installed here."""
    import sys
    import types

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = lambda api_key: None  # pragma: no cover - not reached, no key present
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from ocom_reader.llm.providers.openai import OpenAIProvider

    with pytest.raises(LLMProviderUnavailableError):
        OpenAIProvider(LLMConfig())


# --- ComposedAnswer is never mutated ----------------------------------------


def test_enhance_never_mutates_the_composed_answer() -> None:
    answer = _answer()
    before = answer.model_dump()
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=FakeProvider())

    adapter.enhance(answer)

    assert answer.model_dump() == before


def test_enhance_never_mutates_the_composed_answer_even_on_failure() -> None:
    answer = _answer()
    before = answer.model_dump()
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=RaisingProvider())

    adapter.enhance(answer)

    assert answer.model_dump() == before


# --- Determinism (same input, same fake provider, same output) -----------


def test_enhance_is_deterministic_with_a_deterministic_provider() -> None:
    answer = _answer()
    adapter = LLMAdapter(LLMConfig(provider=LLMProviderName.OPENAI), provider=FakeProvider("consistent text"))

    first = adapter.enhance(answer)
    second = adapter.enhance(answer)

    assert first.model_dump() == second.model_dump()
