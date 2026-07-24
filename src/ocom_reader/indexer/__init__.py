"""Repository Indexer — a deterministic, structural index of this
repository's Markdown documentation.

Deliberately a separate subsystem from adapters/normalizers/core: it
produces no OCOMObject (no object extraction, no semantic
interpretation — this milestone's own scope boundary). It exists to
answer "what documentation exists and where," as the future entry
point for a Retrieval Engine, not to reason about content.
"""

from ocom_reader.indexer.index_builder import RepositoryIndexBuilder
from ocom_reader.indexer.models import DocumentIndexEntry, Heading, InvalidDocument, RepositoryIndex

__all__ = [
    "RepositoryIndexBuilder",
    "RepositoryIndex",
    "DocumentIndexEntry",
    "Heading",
    "InvalidDocument",
]
