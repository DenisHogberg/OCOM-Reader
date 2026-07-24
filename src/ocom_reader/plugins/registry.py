"""PluginRegistry — registration, lookup, ID conflicts, version
compatibility. Tracks manifests and lifecycle state only; never
imports or instantiates anything (that's loader.py/manager.py's job).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocom_reader.plugins.exceptions import PluginCompatibilityError, PluginConflictError, PluginNotFoundError
from ocom_reader.plugins.protocol import PluginManifest, PluginState


def _parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def version_at_least(candidate: str, minimum: str) -> bool:
    return _parse_version(candidate) >= _parse_version(minimum)


@dataclass
class PluginRecord:
    manifest: PluginManifest
    source: str  # "builtin" | f"filesystem:{path}"
    state: PluginState = PluginState.DISCOVERED
    enabled: bool = True
    error: Optional[str] = None


@dataclass
class PluginRegistry:
    reader_version: str
    _records: dict[str, PluginRecord] = field(default_factory=dict)

    def register(self, manifest: PluginManifest, source: str, enabled: bool = True) -> PluginRecord:
        if manifest.id in self._records:
            existing = self._records[manifest.id]
            raise PluginConflictError(
                f"Plugin id {manifest.id!r} is already registered from {existing.source!r} "
                f"— cannot register again from {source!r}."
            )
        if not version_at_least(self.reader_version, manifest.minimum_reader_version):
            raise PluginCompatibilityError(
                f"Plugin {manifest.id!r} requires reader >= {manifest.minimum_reader_version}, "
                f"installed is {self.reader_version}."
            )
        record = PluginRecord(manifest=manifest, source=source, enabled=enabled)
        self._records[manifest.id] = record
        return record

    def unregister(self, plugin_id: str) -> None:
        if plugin_id not in self._records:
            raise PluginNotFoundError(f"No plugin registered with id {plugin_id!r}.")
        del self._records[plugin_id]

    def get(self, plugin_id: str) -> Optional[PluginRecord]:
        return self._records.get(plugin_id)

    def require(self, plugin_id: str) -> PluginRecord:
        record = self.get(plugin_id)
        if record is None:
            raise PluginNotFoundError(f"No plugin registered with id {plugin_id!r}.")
        return record

    def all(self) -> list[PluginRecord]:
        return list(self._records.values())

    def transition(self, plugin_id: str, state: PluginState) -> None:
        self.require(plugin_id).state = state

    def mark_failed(self, plugin_id: str, error: str) -> None:
        record = self.require(plugin_id)
        record.state = PluginState.FAILED
        record.error = error

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self.require(plugin_id).enabled = enabled
