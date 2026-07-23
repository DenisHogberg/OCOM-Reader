"""QueryNormalizer v0.1 — mechanical only.

Implements docs/architecture/OCOM-Runtime-v0.2-Reliability-Design.md
§3's token rules exactly: lowercase, strip punctuation, split, drop
tokens shorter than 2 characters, drop a small fixed stopword list.

Owns tokenization only. Does not own meaning — no stemming, no synonym
expansion, no semantic similarity, no LLM call (that document's "What
QueryNormalizer must NOT own"). Not reused for identity comparison;
`IdentityResolver` has its own independent tokenizer
(`identity/resolver.py`) and this module has no dependency on it.

The stopword list is deliberately minimal — this project's v0.1
limitation, not a claim of linguistic completeness (design doc §8,
Open Question 1). Do not extend it without a concrete failing case to
justify the addition; `test_query_normalizer.py`'s Test 2 exists
specifically to catch an unjustified expansion.
"""

from __future__ import annotations

import re

from ocom_reader.runtime.query.models import NormalizedQuery

MINIMUM_TOKEN_LENGTH = 2

STOPWORDS = frozenset(
    {
        "a", "an", "the",
        "is", "what", "who", "how", "why", "where", "when",
        "of", "for", "to",
    }
)


class QueryNormalizer:
    def normalize(self, raw: str) -> NormalizedQuery:
        text = re.sub(r"[^a-z0-9]+", " ", raw.lower())
        tokens = [
            token
            for token in text.split()
            if len(token) >= MINIMUM_TOKEN_LENGTH and token not in STOPWORDS
        ]
        return NormalizedQuery(raw=raw, tokens=tokens)
