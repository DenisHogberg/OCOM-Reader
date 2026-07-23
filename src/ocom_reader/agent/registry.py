"""ObjectRegistry — candidate search over Storage, via QueryNormalizer + SearchPolicy.

Not a new database: this still wraps Storage.list(), nothing more. Not
Identity Resolution either — that is a separate, larger decision (see
docs/architecture/OCOM-Agent-v0.1-Design.md §6), deliberately out of
scope here. find_candidates() may return zero, one, or several
OCOMObjects; deciding which one is "the" answer is not this
component's job.

Registry owns none of the actual search logic — it is coordination
only, per docs/architecture/OCOM-Runtime-v0.2-Reliability-Design.md.
It does not tokenize a query, does not remove stopwords
(`QueryNormalizer`, runtime/query/), and does not decide which parts
of an object are searchable (`SearchPolicy`, runtime/search/). This
replaces the previous `str(value) for value in obj.metadata.values())`
approach, which produced MILESTONE-004's Limitation 1 — dict key names
(e.g. `"concept"`) leaking into matches.

No ranking, no fuzzy matching, no scoring: a candidate is returned if
any normalized query token appears in its SearchPolicy-computed
searchable text — the same "any term matches" rule this component
already had, just fed by two dedicated collaborators instead of one
inline, unsafe conversion.
"""

from __future__ import annotations

from typing import Optional

from ocom_reader.agent.query import Query
from ocom_reader.core.object import OCOMObject
from ocom_reader.interfaces.storage import Storage
from ocom_reader.runtime.query.normalizer import QueryNormalizer
from ocom_reader.runtime.search.policy import SearchPolicy


class ObjectRegistry:
    def __init__(
        self,
        storage: Storage,
        query_normalizer: Optional[QueryNormalizer] = None,
        search_policy: Optional[SearchPolicy] = None,
    ) -> None:
        self._storage = storage
        self._query_normalizer = query_normalizer or QueryNormalizer()
        self._search_policy = search_policy or SearchPolicy()

    def find_candidates(self, query: Query) -> list[OCOMObject]:
        normalized = self._query_normalizer.normalize(query.text)
        return [obj for obj in self._storage.list() if self._matches(obj, normalized.tokens)]

    def _matches(self, obj: OCOMObject, tokens: list[str]) -> bool:
        text = self._search_policy.searchable_text(obj)
        return any(token in text for token in tokens)
