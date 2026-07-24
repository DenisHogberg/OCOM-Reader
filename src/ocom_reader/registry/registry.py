"""KnowledgeRegistry — the queryable container for RegistryEntry/KnowledgeRelation.

Read-only after construction: built once by RegistryBuilder, matching
RepositoryIndex's own "rebuild from scratch" pattern — no incremental
mutation API. Pure lookups only, no search, no ranking — that stays a
future Retrieval Engine's job (MILESTONE-007-DESIGN.md §Registry
Responsibilities).

`lookup()` and `get()` are the same operation under two names, since
the task's own API sketch listed both without distinguishing them —
kept as a documented alias (see MILESTONE-007.md) rather than two
behaviors with one purpose.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.relations import KnowledgeRelation


class KnowledgeRegistry(BaseModel):
    entries: list[RegistryEntry] = Field(default_factory=list)
    relations: list[KnowledgeRelation] = Field(default_factory=list)

    def lookup(self, registry_id: str) -> Optional[RegistryEntry]:
        for entry in self.entries:
            if entry.registry_id == registry_id:
                return entry
        return None

    def get(self, registry_id: str) -> Optional[RegistryEntry]:
        return self.lookup(registry_id)

    def contains(self, registry_id: str) -> bool:
        return self.lookup(registry_id) is not None

    def neighbors(self, registry_id: str) -> list[RegistryEntry]:
        neighbor_ids = {r.target_id for r in self.relations if r.source_id == registry_id}
        neighbor_ids |= {r.source_id for r in self.relations if r.target_id == registry_id}
        return [entry for entry in self.entries if entry.registry_id in neighbor_ids]

    def related(self, registry_id: str, relation_type: str) -> list[RegistryEntry]:
        target_ids = {
            r.target_id
            for r in self.relations
            if r.source_id == registry_id and r.relation_type == relation_type
        }
        return [entry for entry in self.entries if entry.registry_id in target_ids]
