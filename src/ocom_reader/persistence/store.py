"""PersistentStore — the .ocom/ directory's only reader/writer.

Writes `index.json`, `registry.json`, and `retrieval.json` before
`metadata.json` — a `metadata.json` that exists always describes a
complete, consistent snapshot (never a partial one), which is why
`RepositoryLoader` (loader/) no longer writes on its own: it doesn't
have a KnowledgeRegistry to save alongside the index, and a
metadata.json backed only by a fresh index.json but a stale
registry.json would be exactly the inconsistency this ordering exists
to prevent. `Reader` is the only caller that holds all three artifacts
at once, so it is the only writer.

`registry.json`/`retrieval.json` are written for persistence and
external inspection; `Reader` never reads them back — `KnowledgeRegistry`
is always rebuilt fresh from whatever `RepositoryIndex` is in hand
(`RegistryBuilder.build()` is a cheap, pure, deterministic function),
which sidesteps any "is the stored registry still valid for this
index" staleness question entirely.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from ocom_reader.indexer.models import RepositoryIndex
from ocom_reader.persistence import paths
from ocom_reader.persistence.migrations import CURRENT_STORAGE_VERSION, migrate_to_current
from ocom_reader.persistence.models import FormatCompatibility, StorageMetadata
from ocom_reader.registry.registry import KnowledgeRegistry


def _reader_version() -> str:
    try:
        return version("ocom-reader")
    except PackageNotFoundError:
        return "unknown"


class PersistentStore:
    def __init__(self, repository_root: Path) -> None:
        self._root = Path(repository_root)

    def exists(self) -> bool:
        return paths.metadata_path(self._root).exists()

    def load_metadata(self) -> Optional[StorageMetadata]:
        path = paths.metadata_path(self._root)
        if not path.exists():
            return None
        return StorageMetadata.model_validate(json.loads(path.read_text()))

    def check_compatibility(self) -> FormatCompatibility:
        metadata = self.load_metadata()
        if metadata is None:
            return FormatCompatibility(
                compatible=False,
                stored_version=None,
                current_version=CURRENT_STORAGE_VERSION,
                reason="No stored snapshot found.",
            )
        if metadata.storage_version == CURRENT_STORAGE_VERSION:
            return FormatCompatibility(
                compatible=True,
                stored_version=metadata.storage_version,
                current_version=CURRENT_STORAGE_VERSION,
                reason="Stored version matches the current version.",
            )
        if metadata.storage_version < CURRENT_STORAGE_VERSION:
            return FormatCompatibility(
                compatible=True,
                stored_version=metadata.storage_version,
                current_version=CURRENT_STORAGE_VERSION,
                reason=f"Stored version {metadata.storage_version} is older than "
                f"{CURRENT_STORAGE_VERSION}; will be migrated on load.",
            )
        return FormatCompatibility(
            compatible=False,
            stored_version=metadata.storage_version,
            current_version=CURRENT_STORAGE_VERSION,
            reason=f"Stored version {metadata.storage_version} is newer than this "
            f"Reader's current version {CURRENT_STORAGE_VERSION}.",
        )

    def load_index(self) -> Optional[RepositoryIndex]:
        metadata = self.load_metadata()
        path = paths.index_path(self._root)
        if metadata is None or not path.exists():
            return None
        data = json.loads(path.read_text())
        if metadata.storage_version != CURRENT_STORAGE_VERSION:
            data = migrate_to_current(data, metadata.storage_version)
        return RepositoryIndex.model_validate(data)

    def load_registry(self) -> Optional[KnowledgeRegistry]:
        metadata = self.load_metadata()
        path = paths.registry_path(self._root)
        if metadata is None or not path.exists():
            return None
        data = json.loads(path.read_text())
        if metadata.storage_version != CURRENT_STORAGE_VERSION:
            data = migrate_to_current(data, metadata.storage_version)
        return KnowledgeRegistry.model_validate(data)

    def load_retrieval_metadata(self) -> dict:
        path = paths.retrieval_path(self._root)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def save(
        self,
        index: RepositoryIndex,
        registry: KnowledgeRegistry,
        retrieval_metadata: Optional[dict] = None,
    ) -> None:
        paths.ocom_dir(self._root).mkdir(parents=True, exist_ok=True)

        paths.index_path(self._root).write_text(json.dumps(index.model_dump(mode="json")))
        paths.registry_path(self._root).write_text(json.dumps(registry.model_dump(mode="json")))
        paths.retrieval_path(self._root).write_text(json.dumps(retrieval_metadata or {"ranking_config": {}}))

        existing = self.load_metadata()
        now = datetime.now(timezone.utc)
        metadata = StorageMetadata(
            storage_version=CURRENT_STORAGE_VERSION,
            reader_version=_reader_version(),
            repository_root=str(self._root.resolve()),
            created_at=existing.created_at if existing is not None else now,
            last_updated=now,
        )
        paths.metadata_path(self._root).write_text(metadata.model_dump_json())
