"""RetrievalEngine — finds and ranks RegistryEntry matches for a query.

Does not answer the user — that is M009's job. Does not store state
between calls: every search()/retrieve() call re-derives its result
from the RepositoryIndex/KnowledgeRegistry it was constructed with,
neither of which it ever mutates (see
tests/test_retrieval_engine.py's invariant checks).

Matching is two-tier, and both tiers stay fully explainable via
MatchReason:

  1. Primary matches — a document whose title, a heading, or its
     preview contains a query token (RepositoryIndex data).
  2. Secondary matches — entries connected to a primary match via a
     KnowledgeRelation (builds_on / references / architecture_sequence)
     that did not themselves match the query text. Expansion follows
     relations in both directions (what a primary match builds_on, and
     what builds_on it) — relevance is symmetric even though the
     relation itself is directional. Direction is preserved in
     MatchReason.detail (the primary match's registry_id) for
     explainability, never in the reason kind. This is "getting
     related documents" per this milestone's own requirement, not a
     second, independent search.

No LLM, no embeddings, no semantic search, no fuzzy matching: every
match is a literal substring check against already-extracted,
deterministic Index data, and every relation comes directly from
KnowledgeRegistry (M007) unchanged.
"""

from __future__ import annotations

from ocom_reader.indexer.models import DocumentIndexEntry, RepositoryIndex
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry import KnowledgeRegistry
from ocom_reader.retrieval.models import MatchReason, QueryObject, RetrievalMatch, RetrievalResult
from ocom_reader.retrieval.query_parser import QueryParser
from ocom_reader.retrieval.ranking import Ranker

RELATION_KINDS = ("builds_on", "architecture_sequence", "references")


class RetrievalEngine:
    def __init__(self, index: RepositoryIndex, registry: KnowledgeRegistry) -> None:
        self._index = index
        self._registry = registry
        self._parser = QueryParser()
        self._ranker = Ranker()

    def search(self, query_text: str) -> list[RetrievalMatch]:
        query = self._parser.parse(query_text)
        return self._match(query)

    def retrieve(self, query_text: str) -> RetrievalResult:
        query = self._parser.parse(query_text)
        matches = self._match(query)
        return RetrievalResult(query=query, matches=self._ranker.rank(matches))

    def related(self, registry_id: str) -> list[RegistryEntry]:
        return self._registry.neighbors(registry_id)

    def rank(self, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
        return self._ranker.rank(matches)

    def explain(self, match: RetrievalMatch) -> list[str]:
        return [f"{reason.kind}: {reason.detail}" for reason in match.reasons]

    def _match(self, query: QueryObject) -> list[RetrievalMatch]:
        if not query.tokens:
            return []

        primary = self._primary_matches(query)
        secondary = self._secondary_matches(primary)
        return list(primary.values()) + list(secondary.values())

    def _primary_matches(self, query: QueryObject) -> dict[str, RetrievalMatch]:
        primary: dict[str, RetrievalMatch] = {}
        for document in self._index.entries:
            reasons = self._text_reasons(document, query)
            if not reasons:
                continue
            entry = self._registry.lookup(document.id)
            if entry is None:
                continue  # defensive only — every indexed document has a registry entry in practice
            primary[entry.registry_id] = RetrievalMatch(
                entry=entry,
                reasons=reasons,
                related=[e.registry_id for e in self._registry.neighbors(entry.registry_id)],
            )
        return primary

    def _secondary_matches(self, primary: dict[str, RetrievalMatch]) -> dict[str, RetrievalMatch]:
        secondary: dict[str, RetrievalMatch] = {}
        for registry_id in primary:
            for related_id in self._connected_registry_ids(registry_id):
                if related_id in primary:
                    continue  # already a primary match — never demoted to secondary
                related_entry = self._registry.lookup(related_id)
                if related_entry is None:
                    continue
                relation_type = self._relation_type_between(registry_id, related_id)
                reason = MatchReason(kind=relation_type, detail=registry_id)
                if related_id in secondary:
                    secondary[related_id].reasons.append(reason)
                else:
                    secondary[related_id] = RetrievalMatch(
                        entry=related_entry,
                        reasons=[reason],
                        related=[e.registry_id for e in self._registry.neighbors(related_id)],
                    )
        return secondary

    def _connected_registry_ids(self, registry_id: str) -> list[str]:
        outbound = {
            r.target_id
            for r in self._registry.relations
            if r.source_id == registry_id and r.relation_type in RELATION_KINDS
        }
        inbound = {
            r.source_id
            for r in self._registry.relations
            if r.target_id == registry_id and r.relation_type in RELATION_KINDS
        }
        return sorted(outbound | inbound)

    def _relation_type_between(self, registry_id: str, other_id: str) -> str:
        for r in self._registry.relations:
            if r.source_id == registry_id and r.target_id == other_id and r.relation_type in RELATION_KINDS:
                return r.relation_type
            if r.source_id == other_id and r.target_id == registry_id and r.relation_type in RELATION_KINDS:
                return r.relation_type
        return "references"  # unreachable given _connected_registry_ids' construction; defensive fallback

    def _text_reasons(self, document: DocumentIndexEntry, query: QueryObject) -> list[MatchReason]:
        reasons: list[MatchReason] = []

        title_lower = document.title.lower()
        for token in query.tokens:
            if token in title_lower:
                reasons.append(MatchReason(kind="title_match", detail=token))

        for heading in document.headings:
            heading_lower = heading.text.lower()
            for token in query.tokens:
                if token in heading_lower:
                    reasons.append(MatchReason(kind="heading_match", detail=token))

        preview_lower = document.preview.lower()
        for token in query.tokens:
            if token in preview_lower:
                reasons.append(MatchReason(kind="preview_match", detail=token))

        return reasons
