"""Minimal local MemoryStore implementation.

Mirrors LocalJSONStorage exactly: one JSON file per MemoryEntry, named
after its id. No indexing, no querying, no concurrency handling — the
same "working foundation, not an optimized one" scope Storage's own
first implementation had. No new storage infrastructure, no special
database — reuse of the existing, proven pattern only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from ocom_reader.core.memory import MemoryEntry
from ocom_reader.interfaces.memory_store import MemoryStore


class LocalJSONMemoryStore(MemoryStore):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, entry_id: str) -> Path:
        return self._data_dir / f"{entry_id}.json"

    def save(self, entry: MemoryEntry) -> None:
        self._path_for(entry.id).write_text(entry.model_dump_json(indent=2))

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        path = self._path_for(entry_id)
        if not path.exists():
            return None
        return MemoryEntry.model_validate_json(path.read_text())

    def list(self) -> Iterator[MemoryEntry]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield MemoryEntry.model_validate_json(path.read_text())

    def delete(self, entry_id: str) -> None:
        path = self._path_for(entry_id)
        if path.exists():
            path.unlink()
