"""Persistent Storage — versioned .ocom/ directory (metadata.json,
index.json, registry.json, retrieval.json). See
docs/architecture/MILESTONE-012.md.
"""

from ocom_reader.persistence.migrations import CURRENT_STORAGE_VERSION, migrate_to_current
from ocom_reader.persistence.models import FormatCompatibility, MigrationError, StorageMetadata
from ocom_reader.persistence.store import PersistentStore

__all__ = [
    "PersistentStore",
    "StorageMetadata",
    "FormatCompatibility",
    "MigrationError",
    "CURRENT_STORAGE_VERSION",
    "migrate_to_current",
]
