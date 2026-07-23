"""ObjectRegistry — minimal candidate search over the existing Storage.

Not a new database: this wraps Storage.list() with a plain keyword
overlap filter, nothing more. Not Identity Resolution either — that is
a separate, larger decision (see
docs/architecture/OCOM-Agent-v0.1-Design.md §6), deliberately out of
scope for this first vertical slice. find_candidates() may return zero,
one, or several OCOMObjects; deciding which one is "the" answer is not
this component's job.
"""

from __future__ import annotations

from ocom_reader.agent.query import Query
from ocom_reader.core.object import OCOMObject
from ocom_reader.interfaces.storage import Storage


class ObjectRegistry:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def find_candidates(self, query: Query) -> list[OCOMObject]:
        terms = [t for t in query.text.lower().split() if t]
        return [obj for obj in self._storage.list() if self._matches(obj, terms)]

    def _matches(self, obj: OCOMObject, terms: list[str]) -> bool:
        haystack = self._searchable_text(obj)
        return any(term in haystack for term in terms)

    def _searchable_text(self, obj: OCOMObject) -> str:
        parts = [obj.object_type, *obj.classification]
        parts.extend(str(value) for value in obj.metadata.values())
        return " ".join(parts).lower()
