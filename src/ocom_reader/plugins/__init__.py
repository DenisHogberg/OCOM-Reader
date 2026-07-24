"""Plugin Architecture (M017) — infrastructure through which Reader can
be extended without changing its core. No concrete plugin ships here.
See docs/architecture/MILESTONE-017.md.
"""

from ocom_reader.plugins.context import PluginContext, PluginWorkspaceView
from ocom_reader.plugins.exceptions import (
    PluginCompatibilityError,
    PluginConflictError,
    PluginError,
    PluginInitializationError,
    PluginLoadError,
    PluginManifestError,
    PluginNotFoundError,
)
from ocom_reader.plugins.loader import DiscoveredPlugin, PluginLoader
from ocom_reader.plugins.manager import PluginManager, default_plugin_state_path, default_user_plugin_dir
from ocom_reader.plugins.protocol import Capability, Plugin, PluginManifest, PluginState
from ocom_reader.plugins.registry import PluginRecord, PluginRegistry

__all__ = [
    "PluginManager",
    "PluginRegistry",
    "PluginLoader",
    "PluginContext",
    "PluginWorkspaceView",
    "PluginRecord",
    "DiscoveredPlugin",
    "Plugin",
    "PluginManifest",
    "PluginState",
    "Capability",
    "PluginError",
    "PluginManifestError",
    "PluginConflictError",
    "PluginCompatibilityError",
    "PluginLoadError",
    "PluginInitializationError",
    "PluginNotFoundError",
    "default_plugin_state_path",
    "default_user_plugin_dir",
]
