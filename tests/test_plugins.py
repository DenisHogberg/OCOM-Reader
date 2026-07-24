"""Plugin Architecture (M017).

Filesystem plugins are written to real tmp_path directories (real
plugin.json + plugin.py, really imported) rather than mocked — the
same "prove it against real data before trusting a mock" discipline
used throughout this project. Builtin discovery uses injected fake
classes (`PluginManager(builtin_plugins=[...])`), matching how
production code is meant to supply builtins (never a global list
mutated by tests). A dedicated real-repository section at the bottom
constructs a PluginManager against this project's own repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from ocom_reader.plugins import (
    Capability,
    Plugin,
    PluginCompatibilityError,
    PluginConflictError,
    PluginContext,
    PluginError,
    PluginManager,
    PluginManifest,
    PluginNotFoundError,
    PluginState,
)
from ocom_reader.plugins.loader import PluginLoader
from ocom_reader.plugins.registry import PluginRegistry, version_at_least


def _write_plugin(
    directory: Path,
    plugin_id: str,
    *,
    entry_point: str = "plugin:TestPlugin",
    minimum_reader_version: str = "0.1.0",
    body: Optional[str] = None,
    manifest_overrides: Optional[dict] = None,
) -> Path:
    plugin_dir = directory / plugin_id.replace("-", "_")
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": plugin_id,
        "name": plugin_id.replace("-", " ").title(),
        "version": "1.0.0",
        "author": "Test Author",
        "description": "A test plugin.",
        "entry_point": entry_point,
        "minimum_reader_version": minimum_reader_version,
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
    (plugin_dir / "plugin.py").write_text(
        body
        or f"""
class TestPlugin:
    id = {plugin_id!r}
    name = {manifest["name"]!r}
    version = "1.0.0"
    description = "A test plugin."
    def initialize(self, context):
        self.initialized = True
        self.context = context
    def shutdown(self):
        self.initialized = False
    def capabilities(self):
        from ocom_reader.plugins.protocol import Capability
        return [Capability.UTILITY]
"""
    )
    return plugin_dir


# --- Protocol ---------------------------------------------------------------


def test_a_conforming_object_satisfies_the_plugin_protocol() -> None:
    class Conforming:
        id = "x"
        name = "X"
        version = "1.0"
        description = "d"

        def initialize(self, context):
            pass

        def shutdown(self):
            pass

        def capabilities(self):
            return []

    assert isinstance(Conforming(), Plugin)


def test_an_object_missing_a_method_does_not_satisfy_the_protocol() -> None:
    class Incomplete:
        id = "x"
        name = "X"
        version = "1.0"
        description = "d"

        def initialize(self, context):
            pass

        # no shutdown, no capabilities

    assert isinstance(Incomplete(), Plugin) is False


# --- version_at_least ---------------------------------------------------


def test_version_at_least() -> None:
    assert version_at_least("0.2.0", "0.1.0") is True
    assert version_at_least("0.1.0", "0.1.0") is True
    assert version_at_least("0.0.9", "0.1.0") is False
    assert version_at_least("1.0.0", "0.9.9") is True


# --- PluginRegistry -----------------------------------------------------


def _manifest(plugin_id: str = "a", minimum_reader_version: str = "0.0.1") -> PluginManifest:
    return PluginManifest(
        id=plugin_id, name="A", version="1.0", author="X", description="d",
        entry_point="m:C", minimum_reader_version=minimum_reader_version,
    )


def test_registry_register_and_get() -> None:
    reg = PluginRegistry(reader_version="1.0.0")
    reg.register(_manifest("a"), source="builtin")

    record = reg.get("a")

    assert record is not None
    assert record.state == PluginState.DISCOVERED


def test_registry_duplicate_id_raises_conflict() -> None:
    reg = PluginRegistry(reader_version="1.0.0")
    reg.register(_manifest("a"), source="builtin")

    with pytest.raises(PluginConflictError):
        reg.register(_manifest("a"), source="filesystem:/somewhere")


def test_registry_incompatible_version_raises() -> None:
    reg = PluginRegistry(reader_version="0.1.0")

    with pytest.raises(PluginCompatibilityError):
        reg.register(_manifest("a", minimum_reader_version="99.0.0"), source="builtin")


def test_registry_unregister_unknown_raises() -> None:
    reg = PluginRegistry(reader_version="1.0.0")

    with pytest.raises(PluginNotFoundError):
        reg.unregister("nope")


def test_registry_all_lists_every_record() -> None:
    reg = PluginRegistry(reader_version="1.0.0")
    reg.register(_manifest("a"), source="builtin")
    reg.register(_manifest("b"), source="builtin")

    assert {r.manifest.id for r in reg.all()} == {"a", "b"}


# --- PluginLoader: filesystem discovery ---------------------------------


def test_discover_filesystem_finds_a_real_plugin(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "alpha")
    loader = PluginLoader()

    discovered = loader.discover_filesystem(tmp_path)

    assert len(discovered) == 1
    assert discovered[0].manifest.id == "alpha"


def test_discover_filesystem_on_a_nonexistent_directory_is_empty() -> None:
    loader = PluginLoader()

    assert loader.discover_filesystem(Path("/does/not/exist")) == []


def test_discover_filesystem_skips_a_directory_without_a_manifest(tmp_path: Path) -> None:
    (tmp_path / "not_a_plugin").mkdir()
    loader = PluginLoader()

    assert loader.discover_filesystem(tmp_path) == []


def test_discover_filesystem_skips_an_invalid_json_manifest_and_continues(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "plugin.json").write_text("{ not valid json")
    _write_plugin(tmp_path, "alpha")

    discovered = PluginLoader().discover_filesystem(tmp_path)

    assert [d.manifest.id for d in discovered] == ["alpha"]


def test_discover_filesystem_skips_a_manifest_missing_required_fields(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "plugin.json").write_text(json.dumps({"id": "incomplete"}))
    _write_plugin(tmp_path, "alpha")

    discovered = PluginLoader().discover_filesystem(tmp_path)

    assert [d.manifest.id for d in discovered] == ["alpha"]


def test_instantiate_a_real_filesystem_plugin(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "alpha")
    [discovered] = PluginLoader().discover_filesystem(tmp_path)

    instance = PluginLoader().instantiate(discovered)

    assert instance.id == "alpha"
    assert isinstance(instance, Plugin)


def test_instantiate_two_plugins_named_plugin_py_do_not_collide(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "alpha")
    _write_plugin(tmp_path, "beta")
    discovered = PluginLoader().discover_filesystem(tmp_path)

    instances = [PluginLoader().instantiate(d) for d in discovered]

    assert {i.id for i in instances} == {"alpha", "beta"}


def test_instantiate_with_a_malformed_entry_point_raises(tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, "alpha", entry_point="no-colon-here")
    [discovered] = PluginLoader().discover_filesystem(tmp_path)

    with pytest.raises(PluginError):
        PluginLoader().instantiate(discovered)


def test_instantiate_with_a_missing_class_raises(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "alpha", entry_point="plugin:NoSuchClass")
    [discovered] = PluginLoader().discover_filesystem(tmp_path)

    with pytest.raises(PluginError):
        PluginLoader().instantiate(discovered)


def test_instantiate_an_object_not_satisfying_the_protocol_raises(tmp_path: Path) -> None:
    _write_plugin(
        tmp_path, "alpha",
        body="class TestPlugin:\n    id = 'alpha'\n",  # missing name/version/description/initialize/shutdown/capabilities
    )
    [discovered] = PluginLoader().discover_filesystem(tmp_path)

    with pytest.raises(PluginError):
        PluginLoader().instantiate(discovered)


# --- PluginLoader: builtin discovery -------------------------------------


class _FakeBuiltinPlugin:
    id = "fake-builtin"
    name = "Fake Builtin"
    version = "1.0.0"
    description = "An injected builtin, never shipped for real."
    minimum_reader_version = "0.0.1"

    def initialize(self, context):
        self.initialized = True

    def shutdown(self):
        self.initialized = False

    def capabilities(self):
        return [Capability.UTILITY]


def test_discover_builtin_with_an_injected_class() -> None:
    loader = PluginLoader(builtin_plugins=[_FakeBuiltinPlugin])

    discovered = loader.discover_builtin()

    assert len(discovered) == 1
    assert discovered[0].manifest.id == "fake-builtin"
    assert discovered[0].source == "builtin"


def test_discover_builtin_with_nothing_injected_is_empty() -> None:
    assert PluginLoader().discover_builtin() == []


def test_instantiate_a_builtin_plugin() -> None:
    loader = PluginLoader(builtin_plugins=[_FakeBuiltinPlugin])
    [discovered] = loader.discover_builtin()

    instance = loader.instantiate(discovered)

    assert instance.id == "fake-builtin"


# --- PluginManager: load / lifecycle --------------------------------------


def _manager(tmp_path: Path, plugin_dir: Path, **kwargs) -> PluginManager:
    return PluginManager(
        repository_root=tmp_path,
        user_plugin_dir=plugin_dir,
        state_path=tmp_path / "plugins_state.json",
        **kwargs,
    )


def test_load_registers_and_activates_a_working_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    record = manager.plugin("alpha")
    assert record is not None
    assert record.state == PluginState.ACTIVE
    assert record.error is None


def test_load_passes_a_real_context_to_initialize(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(
        plugin_dir, "alpha",
        body="""
class TestPlugin:
    id = "alpha"
    name = "Alpha"
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        self.seen_root = context.repository_root
        self.seen_version = context.reader_version
    def shutdown(self):
        pass
    def capabilities(self):
        return []
""",
    )
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    assert manager.plugin("alpha").state == PluginState.ACTIVE


def test_a_plugin_whose_initialize_raises_is_marked_failed_but_others_still_load(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(
        plugin_dir, "broken",
        body="""
class TestPlugin:
    id = "broken"
    name = "Broken"
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        raise RuntimeError("boom")
    def shutdown(self):
        pass
    def capabilities(self):
        return []
""",
    )
    _write_plugin(plugin_dir, "healthy")
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    broken = manager.plugin("broken")
    healthy = manager.plugin("healthy")
    assert broken.state == PluginState.FAILED
    assert "boom" in broken.error
    assert healthy.state == PluginState.ACTIVE


def test_a_plugin_whose_shutdown_raises_does_not_break_unload_of_others(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(
        plugin_dir, "broken-shutdown",
        body="""
class TestPlugin:
    id = "broken-shutdown"
    name = "Broken Shutdown"
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        pass
    def shutdown(self):
        raise RuntimeError("shutdown boom")
    def capabilities(self):
        return []
""",
    )
    _write_plugin(plugin_dir, "healthy")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    manager.unload()  # must not raise

    assert manager.plugin("broken-shutdown").state == PluginState.UNLOADED
    assert manager.plugin("healthy").state == PluginState.UNLOADED


def test_a_conflicting_id_across_two_directories_keeps_the_first_and_logs_the_second(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    repo_local = tmp_path / ".ocom" / "plugins"
    _write_plugin(repo_local, "alpha")  # same id, different source
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    assert len(manager.plugins()) == 1
    assert manager.plugin("alpha").source == f"filesystem:{plugin_dir / 'alpha'}"


def test_a_manifest_with_an_unsupported_minimum_version_is_isolated(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "too-new", minimum_reader_version="999.0.0")
    _write_plugin(plugin_dir, "healthy")
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    assert manager.plugin("too-new") is None  # never registered at all
    assert manager.plugin("healthy").state == PluginState.ACTIVE


def test_unload_one_plugin_by_id(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    _write_plugin(plugin_dir, "beta")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    manager.unload("alpha")

    assert manager.plugin("alpha").state == PluginState.UNLOADED
    assert manager.plugin("beta").state == PluginState.ACTIVE


def test_reload_one_plugin_reactivates_it(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.unload("alpha")

    manager.reload("alpha")

    assert manager.plugin("alpha").state == PluginState.ACTIVE


def test_reload_all(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    _write_plugin(plugin_dir, "beta")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    manager.reload()

    assert manager.plugin("alpha").state == PluginState.ACTIVE
    assert manager.plugin("beta").state == PluginState.ACTIVE


# --- enable/disable and persistence -----------------------------------------


def test_disable_unloads_an_active_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    manager.disable("alpha")

    record = manager.plugin("alpha")
    assert record.enabled is False
    assert record.state == PluginState.UNLOADED


def test_disable_state_persists_to_a_new_manager_instance(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.disable("alpha")

    manager2 = _manager(tmp_path, plugin_dir)
    manager2.load()

    record = manager2.plugin("alpha")
    assert record.enabled is False
    assert record.state == PluginState.LOADED  # registered, never initialized


def test_disabled_plugin_is_registered_but_never_initialized_on_a_fresh_load(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.disable("alpha")

    manager2 = _manager(tmp_path, plugin_dir)
    manager2.load()

    assert manager2.plugin("alpha").state != PluginState.ACTIVE


def test_enable_after_disable_and_reload_reactivates(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.disable("alpha")

    manager.enable("alpha")
    manager.reload("alpha")

    assert manager.plugin("alpha").state == PluginState.ACTIVE


def test_enable_unknown_id_raises() -> None:
    manager = PluginManager(repository_root=Path("."), state_path=Path("/tmp/nonexistent-ocom-test-state.json"))

    with pytest.raises(PluginError):
        manager.enable("nope")


def test_enabled_and_disabled_plugins_queries(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    _write_plugin(plugin_dir, "beta")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.disable("beta")

    assert [r.manifest.id for r in manager.enabled_plugins()] == ["alpha"]
    assert [r.manifest.id for r in manager.disabled_plugins()] == ["beta"]


# --- plugins_by_capability -------------------------------------------------


def test_plugins_by_capability_returns_only_active_matching_plugins(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "utility-plugin")  # capabilities() -> [UTILITY]
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    utility_matches = manager.plugins_by_capability(Capability.UTILITY)
    export_matches = manager.plugins_by_capability(Capability.EXPORT)

    assert [r.manifest.id for r in utility_matches] == ["utility-plugin"]
    assert export_matches == []


def test_plugins_by_capability_excludes_a_disabled_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(plugin_dir, "alpha")
    manager = _manager(tmp_path, plugin_dir)
    manager.load()
    manager.disable("alpha")

    assert manager.plugins_by_capability(Capability.UTILITY) == []


def test_plugins_by_capability_excludes_a_failed_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(
        plugin_dir, "broken",
        body="""
class TestPlugin:
    id = "broken"
    name = "Broken"
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        raise RuntimeError("boom")
    def shutdown(self):
        pass
    def capabilities(self):
        return []
""",
    )
    manager = _manager(tmp_path, plugin_dir)
    manager.load()

    assert manager.plugins_by_capability(Capability.UTILITY) == []


# --- PluginContext safety --------------------------------------------------


def test_plugin_receives_a_real_context_with_no_workspace_mutation_methods(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    _write_plugin(
        plugin_dir, "inspector",
        body="""
class TestPlugin:
    id = "inspector"
    name = "Inspector"
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        self.context = context
    def shutdown(self):
        pass
    def capabilities(self):
        return []
""",
    )
    manager = _manager(tmp_path, plugin_dir)

    manager.load()

    instance = manager._instances["inspector"]  # test-only introspection of what the plugin actually received
    context = instance.context
    assert context.repository_root == tmp_path
    assert context.reader_version
    assert not hasattr(context.workspace, "add")
    assert not hasattr(context.workspace, "use")
    assert not hasattr(context.workspace, "remove")


def test_plugin_context_is_a_real_dataclass_with_no_registry_or_engine_fields() -> None:
    import dataclasses

    from ocom_reader.plugins.context import PluginContext

    field_names = {f.name for f in dataclasses.fields(PluginContext)}
    assert field_names == {"repository_root", "workspace", "config", "logger", "reader_version"}


def test_plugin_workspace_view_has_no_mutating_methods() -> None:
    from ocom_reader.plugins.context import PluginWorkspaceView

    view = PluginWorkspaceView(active_repository="x", repositories=["x"])
    assert not hasattr(view, "add")
    assert not hasattr(view, "use")
    assert not hasattr(view, "remove")


# --- Real repository integration --------------------------------------------


def test_plugin_manager_against_the_real_ocom_reader_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    manager = PluginManager(
        repository_root=repo_root,
        user_plugin_dir=tmp_path / "no-plugins-here",
        state_path=tmp_path / "plugins_state.json",
    )

    manager.load()  # no plugins discovered, must not raise

    assert manager.plugins() == []
    assert manager.enabled_plugins() == []
    assert manager.plugins_by_capability(Capability.UTILITY) == []
