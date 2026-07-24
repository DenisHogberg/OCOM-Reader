"""Builtin plugin registry. Empty by design — M017 builds the
discovery mechanism, not a concrete plugin (AI Provider, Markdown/PDF/HTML
export, Search Provider are explicitly out of scope, future milestones).
Tests inject fake plugin classes via PluginManager(builtin_plugins=[...])
rather than appending here, keeping this list production-empty.
"""

from __future__ import annotations

BUILTIN_PLUGINS: list[type] = []
