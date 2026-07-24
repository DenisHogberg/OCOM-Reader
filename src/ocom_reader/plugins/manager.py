"""PluginManager — the one orchestrator. Owns discovery order, error
isolation (one plugin's failure never stops the others), and the
persisted enable/disable state. Never imports RetrievalEngine,
KnowledgeRegistry, Indexer, or Composer.
"""

from __future__ import annotations

import json
import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from ocom_reader.plugins.context import PluginContext, PluginWorkspaceView, build_context
from ocom_reader.plugins.exceptions import PluginError, PluginNotFoundError
from ocom_reader.plugins.loader import PluginLoader
from ocom_reader.plugins.protocol import Capability, Plugin, PluginState
from ocom_reader.plugins.registry import PluginRecord, PluginRegistry

logger = logging.getLogger(__name__)


def _reader_version() -> str:
    try:
        return version("ocom-reader")
    except PackageNotFoundError:
        return "unknown"


def default_plugin_state_path() -> Path:
    return Path.home() / ".ocom_reader" / "plugins_state.json"


def default_user_plugin_dir() -> Path:
    return Path.home() / ".ocom_reader" / "plugins"


class PluginManager:
    def __init__(
        self,
        repository_root: Path,
        builtin_plugins: Optional[list[type]] = None,
        user_plugin_dir: Optional[Path] = None,
        state_path: Optional[Path] = None,
        workspace: Optional[PluginWorkspaceView] = None,
    ) -> None:
        self._repository_root = Path(repository_root)
        self._registry = PluginRegistry(reader_version=_reader_version())
        self._loader = PluginLoader(builtin_plugins=builtin_plugins)
        self._user_plugin_dir = user_plugin_dir or default_user_plugin_dir()
        self._state_path = state_path or default_plugin_state_path()
        self._workspace = workspace or PluginWorkspaceView(active_repository=None, repositories=[])
        self._instances: dict[str, Plugin] = {}
        self._disabled = self._load_disabled_ids()

    @property
    def repository_local_plugin_dir(self) -> Path:
        return self._repository_root / ".ocom" / "plugins"

    def load(self) -> None:
        discovered = (
            self._loader.discover_builtin()
            + self._loader.discover_filesystem(self._user_plugin_dir)
            + self._loader.discover_filesystem(self.repository_local_plugin_dir)
        )
        for item in discovered:
            self._load_one(item)

    def _load_one(self, discovered) -> None:  # noqa: ANN001 - DiscoveredPlugin, avoiding a loader import cycle in type-only context
        plugin_id = discovered.manifest.id
        enabled = plugin_id not in self._disabled
        try:
            self._registry.register(discovered.manifest, discovered.source, enabled=enabled)
        except PluginError as exc:
            logger.error("Plugin %s failed to register: %s", plugin_id, exc)
            return

        try:
            instance = self._loader.instantiate(discovered)
            self._registry.transition(plugin_id, PluginState.LOADED)
            self._instances[plugin_id] = instance
        except PluginError as exc:
            self._registry.mark_failed(plugin_id, str(exc))
            logger.error("Plugin %s failed to load: %s", plugin_id, exc)
            return

        if not enabled:
            return

        try:
            instance.initialize(build_context(self._repository_root, plugin_id, self._workspace))
            self._registry.transition(plugin_id, PluginState.INITIALIZED)
            self._registry.transition(plugin_id, PluginState.ACTIVE)
        except Exception as exc:
            self._registry.mark_failed(plugin_id, f"initialize() failed: {exc}")
            logger.error("Plugin %s failed to initialize: %s", plugin_id, exc)

    def unload(self, plugin_id: Optional[str] = None) -> None:
        targets = [plugin_id] if plugin_id is not None else [r.manifest.id for r in self._registry.all()]
        for pid in targets:
            record = self._registry.get(pid)
            if record is None or record.state not in (PluginState.INITIALIZED, PluginState.ACTIVE):
                continue
            instance = self._instances.get(pid)
            if instance is not None:
                try:
                    instance.shutdown()
                except Exception as exc:
                    logger.error("Plugin %s raised during shutdown(): %s", pid, exc)
            self._registry.transition(pid, PluginState.UNLOADED)

    def reload(self, plugin_id: Optional[str] = None) -> None:
        self.unload(plugin_id)
        targets = [plugin_id] if plugin_id is not None else [r.manifest.id for r in self._registry.all()]
        for pid in targets:
            record = self._registry.get(pid)
            if record is None:
                continue
            self._registry.unregister(pid)
        self._instances = {pid: inst for pid, inst in self._instances.items() if pid not in targets}
        self.load()

    def plugins(self) -> list[PluginRecord]:
        return self._registry.all()

    def plugin(self, plugin_id: str) -> Optional[PluginRecord]:
        return self._registry.get(plugin_id)

    def enabled_plugins(self) -> list[PluginRecord]:
        return [r for r in self._registry.all() if r.enabled]

    def disabled_plugins(self) -> list[PluginRecord]:
        return [r for r in self._registry.all() if not r.enabled]

    def enable(self, plugin_id: str) -> None:
        self._registry.require(plugin_id)  # raises PluginNotFoundError if unknown
        self._disabled.discard(plugin_id)
        self._save_disabled_ids()
        self._registry.set_enabled(plugin_id, True)

    def disable(self, plugin_id: str) -> None:
        self._registry.require(plugin_id)
        self._disabled.add(plugin_id)
        self._save_disabled_ids()
        self._registry.set_enabled(plugin_id, False)
        if self._registry.get(plugin_id).state in (PluginState.INITIALIZED, PluginState.ACTIVE):
            self.unload(plugin_id)

    def plugins_by_capability(self, capability: Capability) -> list[PluginRecord]:
        matches = []
        for record in self._registry.all():
            if record.state != PluginState.ACTIVE:
                continue
            instance = self._instances.get(record.manifest.id)
            if instance is not None and capability in instance.capabilities():
                matches.append(record)
        return matches

    def _load_disabled_ids(self) -> set:
        if not self._state_path.exists():
            return set()
        try:
            data = json.loads(self._state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return set()
        return set(data.get("disabled", []))

    def _save_disabled_ids(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps({"version": 1, "disabled": sorted(self._disabled)}))
