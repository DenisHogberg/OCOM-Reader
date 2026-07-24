"""KnowledgeRelation — a labeled, directed edge between two RegistryEntries.

The relation_type vocabulary is fixed and small, per
MILESTONE-007-DESIGN.md's caution against inventing types without
grounding — only types with an unambiguous, mechanical detection rule
are implemented in v0.1 (see registry_builder.py):

  - "builds_on"              — from a document's own **Builds on:** header line
  - "references"              — any other internal link
  - "architecture_sequence"    — consecutive numbered documents in the same series
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RelationType = Literal["builds_on", "references", "architecture_sequence"]


class KnowledgeRelation(BaseModel):
    source_id: str
    target_id: str
    relation_type: RelationType
