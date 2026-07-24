"""RepositoryLoader — reopen a stored index and detect what changed.

M012 revision: no longer writes. M011's `load()` used to persist a
fresh scan itself via a standalone `JSONIndexStore`; that store is
retired in favor of `persistence.PersistentStore`, which only ever
writes a complete Index+Registry+Retrieval-metadata snapshot together
(see `persistence/store.py`'s module docstring for why a partial write
is unsafe: a fresh index.json paired with a stale registry.json would
silently describe an inconsistent snapshot). `RepositoryLoader` doesn't
hold a `KnowledgeRegistry`, so it can no longer be the writer — `Reader`
is, since it's the only component that holds all three artifacts at
once. `load()`/`reopen()`/`detect_changes()`/`check_compatibility()`
keep their original signatures and return types; only the write
side-effect is gone.

Still "correctness-first incremental," not "performance-first": `load()`
always runs a full `RepositoryIndexBuilder` scan (see MILESTONE-011.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ocom_reader.indexer.index_builder import RepositoryIndexBuilder
from ocom_reader.indexer.models import RepositoryIndex
from ocom_reader.loader.models import ChangeSet, FormatCompatibility
from ocom_reader.persistence.store import PersistentStore


class RepositoryLoader:
    def load(self, repository_root: Path) -> RepositoryIndex:
        previous = self.reopen(repository_root)
        fresh = RepositoryIndexBuilder(repository_root).build()

        if previous is not None and not self.detect_changes(previous, fresh).has_changes:
            return previous

        return fresh

    def reopen(self, repository_root: Path) -> Optional[RepositoryIndex]:
        return PersistentStore(repository_root).load_index()

    def detect_changes(self, previous: RepositoryIndex, current: RepositoryIndex) -> ChangeSet:
        previous_by_id = {entry.id: entry for entry in previous.entries}
        current_by_id = {entry.id: entry for entry in current.entries}

        added = sorted(set(current_by_id) - set(previous_by_id))
        removed = sorted(set(previous_by_id) - set(current_by_id))
        modified = sorted(
            doc_id
            for doc_id in (set(current_by_id) & set(previous_by_id))
            if current_by_id[doc_id].content_hash != previous_by_id[doc_id].content_hash
        )
        return ChangeSet(added=added, modified=modified, removed=removed)

    def check_compatibility(self, repository_root: Path) -> FormatCompatibility:
        return PersistentStore(repository_root).check_compatibility()
