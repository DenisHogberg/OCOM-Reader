"""QueryParser — raw query string -> QueryObject.

Reuses runtime.query.normalizer.QueryNormalizer for tokenization
rather than reimplementing lowercase/punctuation/stopword handling —
that component is already built, tested, and proven deterministic
(MILESTONE-005). No NLP, no semantic analysis: QueryObject only ever
carries mechanically normalized tokens, the same discipline
QueryNormalizer itself was built under.
"""

from __future__ import annotations

from typing import Optional

from ocom_reader.retrieval.models import QueryObject
from ocom_reader.runtime.query.normalizer import QueryNormalizer


class QueryParser:
    def __init__(self, normalizer: Optional[QueryNormalizer] = None) -> None:
        self._normalizer = normalizer or QueryNormalizer()

    def parse(self, text: str) -> QueryObject:
        normalized = self._normalizer.normalize(text)
        return QueryObject(raw=text, tokens=normalized.tokens)
