"""Optional LLM Layer (M019) — presentation-only natural-language
generation sitting strictly after `ComposedAnswer`. `Reader` never
imports from this package; this package never imports `Reader`,
`RetrievalEngine`, `KnowledgeRegistry`, or `Indexer`. See
docs/architecture/MILESTONE-019.md.
"""

from ocom_reader.llm.adapter import LLMAdapter
from ocom_reader.llm.exceptions import LLMError, LLMProviderUnavailableError
from ocom_reader.llm.models import LLMConfig, LLMProviderName, LLMResult
from ocom_reader.llm.protocol import LLMProvider

__all__ = [
    "LLMAdapter",
    "LLMConfig",
    "LLMProviderName",
    "LLMResult",
    "LLMProvider",
    "LLMError",
    "LLMProviderUnavailableError",
]
