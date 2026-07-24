"""PluginContext — the only thing a plugin ever receives. No field here
is (or wraps) RetrievalEngine, KnowledgeRegistry, Indexer, Composer, or
the real WorkspaceManager — `workspace` is a frozen snapshot with no
mutating methods, structurally incapable of registering/switching
repositories, not just conventionally discouraged from it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional


def _reader_version() -> str:
    try:
        return version("ocom-reader")
    except PackageNotFoundError:
        return "unknown"


@dataclass(frozen=True)
class PluginWorkspaceView:
    active_repository: Optional[str]
    repositories: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginContext:
    repository_root: Path
    workspace: PluginWorkspaceView
    config: dict
    logger: logging.Logger
    reader_version: str = field(default_factory=_reader_version)


def build_context(
    repository_root: Path,
    plugin_id: str,
    workspace: Optional[PluginWorkspaceView] = None,
    config: Optional[dict] = None,
) -> PluginContext:
    return PluginContext(
        repository_root=Path(repository_root),
        workspace=workspace or PluginWorkspaceView(active_repository=None, repositories=[]),
        config=config or {},
        logger=logging.getLogger(f"ocom_reader.plugins.{plugin_id}"),
    )
