"""Plugin exception hierarchy — every failure mode named explicitly so
PluginManager's error-isolation loop (manager.py) can log something
specific, never a bare `except Exception`.
"""

from __future__ import annotations


class PluginError(Exception):
    pass


class PluginManifestError(PluginError):
    """A plugin.json failed to parse or didn't match PluginManifest."""


class PluginConflictError(PluginError):
    """Two discovered plugins declared the same id."""


class PluginCompatibilityError(PluginError):
    """A plugin's minimum_reader_version exceeds the installed version."""


class PluginLoadError(PluginError):
    """The entry_point module/class could not be imported or instantiated,
    or the instantiated object doesn't satisfy the Plugin protocol."""


class PluginInitializationError(PluginError):
    """A plugin's initialize(context) raised."""


class PluginNotFoundError(PluginError):
    """No plugin is registered under the given id."""
