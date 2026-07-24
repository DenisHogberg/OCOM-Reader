"""WorkspaceManager — a name-to-path registry and an active-repository
pointer. Never constructs a RetrievalEngine, KnowledgeRegistry, or
AnswerComposer, and never imports them — the only persistence-layer
calls it makes (`storage_path`/`is_initialized`) are pure path
arithmetic and an existence check, not persistence I/O or retrieval.
See MILESTONE-016-DESIGN.md for the full layering rationale.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocom_reader.persistence import paths as persistence_paths
from ocom_reader.persistence.store import PersistentStore
from ocom_reader.workspace.models import WorkspaceEntry, WorkspaceError, WorkspaceState


def default_workspace_path() -> Path:
    return Path.home() / ".ocom_reader" / "workspace.json"


class WorkspaceManager:
    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._state_path = state_path or default_workspace_path()
        self._state = self._load()

    def add(self, name: str, path: Path) -> WorkspaceEntry:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise WorkspaceError(f"Not a directory: {resolved}")
        if self._find(name) is not None:
            raise WorkspaceError(f"A repository named {name!r} is already registered.")

        entry = WorkspaceEntry(name=name, path=str(resolved), added_at=datetime.now(timezone.utc))
        self._state.entries.append(entry)
        if self._state.active is None:
            self._state.active = name
        self._save()
        return entry

    def list(self) -> list[WorkspaceEntry]:
        return list(self._state.entries)

    def use(self, name: str) -> WorkspaceEntry:
        entry = self._find(name)
        if entry is None:
            raise WorkspaceError(f"No repository named {name!r} is registered.")
        self._state.active = name
        self._save()
        return entry

    def remove(self, name: str) -> None:
        entry = self._find(name)
        if entry is None:
            raise WorkspaceError(f"No repository named {name!r} is registered.")
        self._state.entries = [e for e in self._state.entries if e.name != name]
        if self._state.active == name:
            self._state.active = None
        self._save()

    def active(self) -> Optional[WorkspaceEntry]:
        if self._state.active is None:
            return None
        return self._find(self._state.active)

    def resolve(self, name: Optional[str] = None) -> Path:
        if name is not None:
            entry = self._find(name)
            if entry is None:
                raise WorkspaceError(f"No repository named {name!r} is registered.")
            return Path(entry.path)
        active = self.active()
        if active is None:
            raise WorkspaceError("No active repository. Use 'repo use <name>' or pass --repo.")
        return Path(active.path)

    def storage_path(self, name: str) -> Path:
        entry = self._find(name)
        if entry is None:
            raise WorkspaceError(f"No repository named {name!r} is registered.")
        return persistence_paths.ocom_dir(Path(entry.path))

    def is_initialized(self, name: str) -> bool:
        entry = self._find(name)
        if entry is None:
            raise WorkspaceError(f"No repository named {name!r} is registered.")
        return PersistentStore(Path(entry.path)).exists()

    def _find(self, name: str) -> Optional[WorkspaceEntry]:
        for entry in self._state.entries:
            if entry.name == name:
                return entry
        return None

    def _load(self) -> WorkspaceState:
        if not self._state_path.exists():
            return WorkspaceState()
        return WorkspaceState.model_validate(json.loads(self._state_path.read_text()))

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(self._state.model_dump_json())
