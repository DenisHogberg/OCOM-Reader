"""Web UI internal API — handler functions only, no HTTP concerns (that's
server.py's job). Every function is one Reader/WorkspaceManager/PluginManager
call plus `.model_dump(mode="json")`, mirroring commands.py's own "one
Reader call plus presentation" discipline — just producing dicts
instead of formatted strings. No new matching, ranking, or composition
logic; this is the same internal API a future IDE integration could
call directly.

Repository selection is read-only with respect to shared state: `repo`
never mutates `workspace.json`'s active pointer — see
MILESTONE-018-DESIGN.md for why (two browser tabs, or a browser tab and
a terminal, must never fight over one shared "active" repository).
"""

from __future__ import annotations

import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from ocom_reader.plugins import PluginManager
from ocom_reader.reader import Reader
from ocom_reader.workspace import WorkspaceError, WorkspaceManager

# A single process-wide lock around Reader construction (build-and-maybe-save).
# Closes a real race: two concurrent requests against the same repository
# could otherwise both decide .ocom/ needs rebuilding and both call
# PersistentStore.save() at once, producing a torn snapshot (save() writes
# four files sequentially, not atomically). Deliberate simplicity over
# per-repository locking — see MILESTONE-018-DESIGN.md.
_construction_lock = threading.Lock()


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def resolve_repo_path(repo_name: Optional[str], default_repo: Path, workspace: WorkspaceManager) -> Path:
    if repo_name is not None:
        try:
            return workspace.resolve(repo_name)
        except WorkspaceError as exc:
            raise ApiError(str(exc), status=404) from exc
    active = workspace.active()
    if active is not None:
        return Path(active.path)
    return default_repo


def _build_reader(repo_path: Path, use_persistence: bool) -> Reader:
    with _construction_lock:
        return Reader(repo_path, use_persistence=use_persistence)


def get_health() -> dict:
    try:
        reader_version = version("ocom-reader")
    except PackageNotFoundError:
        reader_version = "unknown"
    return {"status": "ok", "reader_version": reader_version}


def get_workspace(workspace: WorkspaceManager) -> dict:
    entries = workspace.list()
    active = workspace.active()
    return {
        "repositories": [
            {"name": e.name, "path": e.path, "active": active is not None and e.name == active.name}
            for e in entries
        ],
        "active": active.name if active else None,
    }


def get_plugins(repo_path: Path, plugin_kwargs: dict) -> dict:
    manager = PluginManager(repository_root=repo_path, **plugin_kwargs)
    manager.load()
    return {
        "plugins": [
            {
                "id": r.manifest.id,
                "name": r.manifest.name,
                "version": r.manifest.version,
                "state": r.state.value,
                "enabled": r.enabled,
                "error": r.error,
            }
            for r in manager.plugins()
        ]
    }


def get_ask(repo_path: Path, query: str, use_persistence: bool) -> dict:
    if not query:
        raise ApiError("Missing required query parameter 'q'.")
    reader = _build_reader(repo_path, use_persistence)
    return reader.answer(query).model_dump(mode="json")


def get_search(repo_path: Path, query: str, use_persistence: bool) -> dict:
    if not query:
        raise ApiError("Missing required query parameter 'q'.")
    reader = _build_reader(repo_path, use_persistence)
    matches = reader.search(query)
    return {"query": query, "matches": [m.model_dump(mode="json") for m in matches]}


def get_related(repo_path: Path, registry_id: str, use_persistence: bool) -> dict:
    if not registry_id:
        raise ApiError("Missing required query parameter 'id'.")
    reader = _build_reader(repo_path, use_persistence)
    entries = reader.related(registry_id)
    return {"registry_id": registry_id, "related": [e.model_dump(mode="json") for e in entries]}


def get_explain(repo_path: Path, query: str, use_persistence: bool) -> dict:
    if not query:
        raise ApiError("Missing required query parameter 'q'.")
    reader = _build_reader(repo_path, use_persistence)
    documents = reader.explain(query)
    return {"query": query, "documents": [d.model_dump(mode="json") for d in documents]}
