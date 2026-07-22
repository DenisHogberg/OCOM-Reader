"""Minimal local Storage implementation.

One JSON file per OCOMObject, named after its identity. No indexing,
no querying, no concurrency handling — Phase 1 needs a working
foundation, not an optimized one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from ocom_reader.core.object import OCOMObject
from ocom_reader.interfaces.storage import Storage


class LocalJSONStorage(Storage):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, identity: str) -> Path:
        return self._data_dir / f"{identity}.json"

    def save(self, obj: OCOMObject) -> None:
        self._path_for(obj.identity).write_text(obj.model_dump_json(indent=2))

    def get(self, identity: str) -> Optional[OCOMObject]:
        path = self._path_for(identity)
        if not path.exists():
            return None
        return OCOMObject.model_validate_json(path.read_text())

    def list(self) -> Iterator[OCOMObject]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield OCOMObject.model_validate_json(path.read_text())

    def delete(self, identity: str) -> None:
        path = self._path_for(identity)
        if path.exists():
            path.unlink()
