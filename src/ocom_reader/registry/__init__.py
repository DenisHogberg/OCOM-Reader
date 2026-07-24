"""Knowledge Registry — a structured, pointer-only knowledge layer over
RepositoryIndex. See docs/architecture/MILESTONE-007-DESIGN.md and
docs/architecture/MILESTONE-007.md.
"""

from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry import KnowledgeRegistry
from ocom_reader.registry.registry_builder import RegistryBuilder
from ocom_reader.registry.relations import KnowledgeRelation

__all__ = ["RegistryEntry", "KnowledgeRelation", "KnowledgeRegistry", "RegistryBuilder"]
