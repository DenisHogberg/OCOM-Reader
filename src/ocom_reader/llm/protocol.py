"""LLMProvider Protocol — the entire contract a provider implements.
`typing.Protocol`, matching M017's Plugin Protocol precedent: no base
class to import, `@runtime_checkable` so `LLMAdapter` can validate an
injected test double the same way `PluginLoader` validates plugins.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, prompt: str, *, timeout: float) -> str: ...
