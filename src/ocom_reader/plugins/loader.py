"""PluginLoader — discovery and instantiation only. No registry
mutation, no lifecycle tracking, no error swallowing: every method
either returns a result or raises a specific PluginError. Isolating
failures across multiple plugins is PluginManager's job, not this
one's ("Loader отвечает только за загрузку. Никакой бизнес-логики").
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from ocom_reader.plugins.exceptions import PluginLoadError, PluginManifestError
from ocom_reader.plugins.protocol import Plugin, PluginManifest

logger = logging.getLogger(__name__)

BUILTIN = "builtin"


@dataclass
class DiscoveredPlugin:
    manifest: PluginManifest
    source: str
    loader_ref: Union[type, Path]  # a class for builtin, a plugin directory for filesystem


class PluginLoader:
    def __init__(self, builtin_plugins: Optional[list[type]] = None) -> None:
        self._builtin_plugins = builtin_plugins or []

    def discover_builtin(self) -> list[DiscoveredPlugin]:
        discovered = []
        for plugin_cls in self._builtin_plugins:
            manifest = self._manifest_from_class(plugin_cls)
            discovered.append(DiscoveredPlugin(manifest=manifest, source=BUILTIN, loader_ref=plugin_cls))
        return discovered

    def discover_filesystem(self, directory: Path) -> list[DiscoveredPlugin]:
        """A directory whose plugin.json is missing/unparseable/invalid
        cannot be given an id (the manifest itself is what's broken),
        so there is nothing to register as a "failed" plugin for it —
        it is logged and skipped, isolated from every other directory,
        exactly like a broken import or a failing initialize() is
        isolated once a plugin does have a valid id (PluginManager)."""
        directory = Path(directory)
        if not directory.is_dir():
            return []
        discovered = []
        for plugin_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
            manifest_path = plugin_dir / "plugin.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = self._load_manifest(manifest_path)
            except PluginManifestError as exc:
                logger.error("Skipping %s: %s", plugin_dir, exc)
                continue
            discovered.append(
                DiscoveredPlugin(manifest=manifest, source=f"filesystem:{plugin_dir}", loader_ref=plugin_dir)
            )
        return discovered

    def instantiate(self, discovered: DiscoveredPlugin) -> Plugin:
        if isinstance(discovered.loader_ref, Path):
            plugin_cls = self._import_from_directory(discovered.loader_ref, discovered.manifest.entry_point)
        else:
            plugin_cls = discovered.loader_ref

        try:
            instance = plugin_cls()
        except Exception as exc:
            raise PluginLoadError(f"Could not instantiate plugin {discovered.manifest.id!r}: {exc}") from exc

        if not isinstance(instance, Plugin):
            raise PluginLoadError(
                f"Plugin {discovered.manifest.id!r} ({plugin_cls!r}) does not satisfy the Plugin protocol "
                "(missing id/name/version/description or initialize/shutdown/capabilities)."
            )
        return instance

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        try:
            data = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginManifestError(f"Could not read/parse {manifest_path}: {exc}") from exc
        try:
            return PluginManifest.model_validate(data)
        except Exception as exc:
            raise PluginManifestError(f"Invalid manifest at {manifest_path}: {exc}") from exc

    def _manifest_from_class(self, plugin_cls: type) -> PluginManifest:
        # Builtin plugins declare their manifest fields as class attributes
        # (id/name/version/description already required by the Plugin
        # protocol) plus `author`/`entry_point`/`minimum_reader_version`
        # for the ones a manifest needs but the protocol doesn't.
        try:
            return PluginManifest(
                id=plugin_cls.id,
                name=plugin_cls.name,
                version=plugin_cls.version,
                author=getattr(plugin_cls, "author", "unknown"),
                description=plugin_cls.description,
                entry_point=f"{plugin_cls.__module__}:{plugin_cls.__name__}",
                minimum_reader_version=getattr(plugin_cls, "minimum_reader_version", "0.0.0"),
            )
        except AttributeError as exc:
            raise PluginManifestError(f"Builtin plugin class {plugin_cls!r} is missing a required field: {exc}") from exc

    def _import_from_directory(self, plugin_dir: Path, entry_point: str) -> type:
        if ":" not in entry_point:
            raise PluginLoadError(f"Malformed entry_point {entry_point!r} (expected 'module:ClassName').")
        module_name, class_name = entry_point.split(":", 1)
        module_path = plugin_dir / f"{module_name}.py"
        if not module_path.exists():
            raise PluginLoadError(f"Entry point module not found: {module_path}")

        # A unique sys.modules key per plugin directory, so two plugins
        # each named "plugin.py" never collide.
        unique_name = f"ocom_reader_plugin_{plugin_dir.name}_{module_name}"
        spec = importlib.util.spec_from_file_location(unique_name, module_path)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Could not load module spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise PluginLoadError(f"Error executing {module_path}: {exc}") from exc

        plugin_cls = getattr(module, class_name, None)
        if plugin_cls is None:
            raise PluginLoadError(f"{module_path} has no attribute {class_name!r}.")
        return plugin_cls
