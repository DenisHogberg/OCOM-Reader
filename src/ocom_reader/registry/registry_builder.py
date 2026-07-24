"""RegistryBuilder — builds a KnowledgeRegistry from a RepositoryIndex.

Deterministic, mechanical rules only, per
docs/architecture/MILESTONE-007-DESIGN.md and MILESTONE-007.md:

  - One RegistryEntry per indexed document, 1:1, pointer-only — no
    title, no headings, no content copied onto the entry.
  - "builds_on" relations: from indexer.DocumentIndexEntry.
    builds_on_links (each document's own **Builds on:** header line,
    already resolved to other indexed documents by the Index).
  - "references" relations: indexer.DocumentIndexEntry.internal_links,
    excluding whatever a "builds_on" relation between the same pair
    already claims — a link is not double-labeled.
  - "architecture_sequence" relations: consecutive numbered documents
    within the same series (ADR-NNN, MILESTONE-NNN), derived purely
    from each entry's own document_id — no additional Index data
    needed.

No LLM, no embeddings, no fuzzy matching, no entity extraction — every
relation is derived from data RepositoryIndex already states
explicitly, or from an entry's own id. RepositoryIndex is read only;
nothing here mutates it (see tests/test_knowledge_registry.py's
invariant checks).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from ocom_reader.indexer.models import RepositoryIndex
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry import KnowledgeRegistry
from ocom_reader.registry.relations import KnowledgeRelation

SEQUENCE_PATTERN = re.compile(r"^(ADR|MILESTONE)-(\d+)")


class RegistryBuilder:
    def build(self, index: RepositoryIndex) -> KnowledgeRegistry:
        entries = self._build_entries(index)
        entry_ids = {entry.registry_id for entry in entries}

        builds_on = self._builds_on_relations(index, entry_ids)
        claimed = {(r.source_id, r.target_id) for r in builds_on}
        references = self._reference_relations(index, entry_ids, claimed)
        sequence = self._sequence_relations(entries)

        return KnowledgeRegistry(entries=entries, relations=[*builds_on, *references, *sequence])

    def _build_entries(self, index: RepositoryIndex) -> list[RegistryEntry]:
        return [
            RegistryEntry(
                registry_id=document.id,
                document_id=document.id,
                entry_type=document.document_type,
            )
            for document in index.entries
        ]

    def _builds_on_relations(self, index: RepositoryIndex, entry_ids: set) -> list[KnowledgeRelation]:
        relations = []
        for document in index.entries:
            for target_id in document.builds_on_links:
                if target_id in entry_ids and target_id != document.id:
                    relations.append(
                        KnowledgeRelation(source_id=document.id, target_id=target_id, relation_type="builds_on")
                    )
        return relations

    def _reference_relations(self, index: RepositoryIndex, entry_ids: set, claimed: set) -> list[KnowledgeRelation]:
        relations = []
        for document in index.entries:
            for target_id in document.internal_links:
                if target_id not in entry_ids or target_id == document.id:
                    continue
                if (document.id, target_id) in claimed:
                    continue  # already labeled "builds_on" — no double-labeling the same pair
                relations.append(
                    KnowledgeRelation(source_id=document.id, target_id=target_id, relation_type="references")
                )
        return relations

    def _sequence_relations(self, entries: list[RegistryEntry]) -> list[KnowledgeRelation]:
        series: dict[str, list[tuple[int, str]]] = {}
        for entry in entries:
            filename = PurePosixPath(entry.document_id).name
            match = SEQUENCE_PATTERN.match(filename)
            if match:
                series.setdefault(match.group(1), []).append((int(match.group(2)), entry.registry_id))

        relations = []
        for members in series.values():
            members.sort()
            for (_, current_id), (_, next_id) in zip(members, members[1:]):
                relations.append(
                    KnowledgeRelation(source_id=current_id, target_id=next_id, relation_type="architecture_sequence")
                )
        return relations
