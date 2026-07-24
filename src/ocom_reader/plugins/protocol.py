"""Plugin Protocol, Manifest, Capability, and lifecycle State — the
entire contract a plugin author needs. Deliberately imports nothing
from retrieval/registry/indexer/composer, and never will: a plugin
only ever receives a PluginContext (context.py).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from ocom_reader.plugins.context import PluginContext


class Capability(str, Enum):
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    INDEXER = "INDEXER"
    RENDERER = "RENDERER"
    COMMAND = "COMMAND"
    AI_PROVIDER = "AI_PROVIDER"
    UTILITY = "UTILITY"


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    FAILED = "failed"
    UNLOADED = "unloaded"


class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    author: str
    description: str
    entry_point: str
    minimum_reader_version: str


@runtime_checkable
class Plugin(Protocol):
    id: str
    name: str
    version: str
    description: str

    def initialize(self, context: "PluginContext") -> None: ...

    def shutdown(self) -> None: ...

    def capabilities(self) -> list[Capability]: ...
