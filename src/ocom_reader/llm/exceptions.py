"""LLM exception hierarchy. `LLMAdapter.enhance()` never lets any of
these escape — every one is caught and turned into an `LLMResult`
with a `fallback_reason` instead. Defined so provider code has
something specific to raise, not because callers are expected to
catch them directly.
"""

from __future__ import annotations


class LLMError(Exception):
    pass


class LLMProviderUnavailableError(LLMError):
    """The configured provider's SDK isn't installed, or construction
    otherwise failed before any network call was attempted."""
