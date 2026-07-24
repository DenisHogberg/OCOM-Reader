# MILESTONE-017: Plugin Architecture

**Date:** 2026-07-24
**Status:** Frozen — infrastructure only, no concrete plugin ships; Reader core untouched.
**Builds on:** [MILESTONE-017-DESIGN.md](MILESTONE-017-DESIGN.md), [MILESTONE-016](MILESTONE-016.md)

## Objective

Infrastructure through which Reader can be extended without changing
its core — not a single concrete plugin. AI Provider, Markdown/PDF/HTML
export, Search Provider, remote plugins, a marketplace, auto-updates,
and dependency resolution between plugins are all explicitly out of
scope, per the task's own list — future milestones.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `Capability`, `PluginState`, `PluginManifest`, `Plugin` (Protocol) | `plugins/protocol.py` | New |
| `PluginContext`, `PluginWorkspaceView`, `build_context` | `plugins/context.py` | New |
| Exception hierarchy | `plugins/exceptions.py` | New |
| `PluginRegistry`, `PluginRecord`, `version_at_least` | `plugins/registry.py` | New |
| `PluginLoader`, `DiscoveredPlugin` | `plugins/loader.py` | New |
| `PluginManager` | `plugins/manager.py` | New |
| `BUILTIN_PLUGINS = []` | `plugins/builtin/__init__.py` | New |
| `plugin list/info/enable/disable/reload` | `cli.py` | Revised |
| `plugin list/info/enable/disable/reload` REPL commands | `interactive.py` | Revised |

## Architectural Confirmation

```
git diff --stat -- retrieval/ registry/ indexer/ composer/   → empty
grep -rn "^from ocom_reader\.(retrieval|registry|indexer|composer)" plugins/   → empty
```

Both checked directly, not assumed. The two docstring hits for
`RetrievalEngine`/`KnowledgeRegistry`/etc. in `context.py`/`manager.py`
are prose *explaining* the constraint, not imports. `plugins/` imports
nothing beyond stdlib, `pydantic`, and its own siblings.

## The Protocol: `typing.Protocol`, Not ABC

`@runtime_checkable` — a plugin author never imports an OCOM Reader
base class; `PluginLoader.instantiate()` validates a loaded object with
`isinstance(instance, Plugin)` before treating it as one, verified to
correctly reject an object missing a method *or* a plain attribute
(`test_an_object_missing_a_method_does_not_satisfy_the_protocol`) —
checked directly against Python's runtime_checkable behavior before
building anything around the assumption.

## Context: the Only Thing a Plugin Sees

```python
@dataclass(frozen=True)
class PluginContext:
    repository_root: Path
    workspace: PluginWorkspaceView   # frozen snapshot, no add/use/remove
    config: dict
    logger: logging.Logger
    reader_version: str
```

`PluginWorkspaceView` has no mutating methods — not a convention, a
structural fact (`test_plugin_workspace_view_has_no_mutating_methods`,
`test_plugin_receives_a_real_context_with_no_workspace_mutation_methods`
via a real plugin's actually-received context object, not a mock).
`config` is an honest empty-dict placeholder — no per-plugin
configuration source was asked for beyond the field existing, the same
grounded-placeholder discipline M012's `retrieval.json` used.

## Discovery Order (documented, tested, not just claimed)

1. **builtin** — injected `builtin_plugins: list[type]` (production: `[]`).
2. **user** — `~/.ocom_reader/plugins/*/`.
3. **repository-local** — `<repository_root>/.ocom/plugins/*/`.

IDs never silently override across sources — a duplicate raises
`PluginConflictError`, logged and isolated by `PluginManager`, keeping
only the first-discovered registration
(`test_a_conflicting_id_across_two_directories_keeps_the_first_and_logs_the_second`,
verified against two real directories, not a mock).

## Lifecycle

```
discovered → loaded → initialized → active
                │            │
                └──────┴──→ failed
active/initialized → unloaded
```

`initialized`→`active` happens in the same step *if* the plugin is
enabled; a disabled plugin is registered and instantiated (`loaded`)
but never initialized, so it can be inspected (`plugin info`) without
running any of its code.

## A Real Isolation Bug Found During Verification (and fixed)

The design doc's own real-plugin verification pass (a working plugin
directory alongside a deliberately broken one) caught a genuine bug
before any test was written: `PluginLoader.discover_filesystem()`
originally let a `PluginManifestError` from one broken `plugin.json`
propagate straight out of `PluginManager.load()`'s list-concatenation
expression, crashing discovery of **every** plugin, not just the
broken one — exactly the failure mode "Error Isolation" exists to
prevent. Fixed by catching `PluginManifestError` per-directory inside
`discover_filesystem()` itself and logging+skipping — a directory
whose manifest can't be parsed has no `id` to register a `failed`
record under, so skip-and-log (not a synthetic failed record) is the
correct outcome, not a shortcut. Re-verified against the same real
fixture directories afterward. Named here in full, the same discipline
M013's late-binding bug and M015's paging hang were both documented,
not silently patched.

## Error Isolation, Proven With Real Plugins

Before any test was written: a directory with `{ not valid json` (skipped,
logged, others unaffected), a plugin whose `initialize()` raises
(marked `failed` with the real exception message, others unaffected),
and — added while writing tests — a plugin whose `shutdown()` raises
(caught during `unload()`, other plugins still get their `shutdown()`
called). All three are now regression tests
(`test_a_plugin_whose_initialize_raises_is_marked_failed_but_others_still_load`,
`test_a_plugin_whose_shutdown_raises_does_not_break_unload_of_others`,
`test_discover_filesystem_skips_an_invalid_json_manifest_and_continues`).

## Enable/Disable Persistence

`~/.ocom_reader/plugins_state.json` (`{"version": 1, "disabled": [...]}`),
overridable via `--plugin-state-file`/constructor for tests, mirroring
M016's `workspace.json` precedent exactly. `disable()` on an
active/initialized plugin also calls `unload()` immediately, so the
running session reflects the change without waiting for a `reload`.

## Test-Hygiene Consistency With M016

Every plugin-related test uses `tmp_path`-scoped `state_path`/`user_plugin_dir`
— none touch the real `~/.ocom_reader/`, extending the isolated-home
discipline M016 already established for `test_cli.py`/`test_interactive.py`.

## Test Results

- `tests/test_plugins.py`: **43 passed** — protocol conformance (positive
  and negative), version comparison, registry (register, duplicate ID,
  incompatible version, unregister unknown, listing), real filesystem
  discovery and instantiation (including two plugins both named
  `plugin.py` not colliding), malformed entry_point, missing class,
  an object failing the protocol check, injected builtin discovery,
  full manager lifecycle (load/unload/reload, both isolation bugs
  above, ID conflicts, incompatible-version isolation), enable/disable
  (unloads immediately, persists across manager instances, re-enable +
  reload reactivates, unknown id raises), `plugins_by_capability`
  (matches, excludes disabled, excludes failed), context safety, and
  real-repository integration (an empty discovery pass against this
  project's own repository, proving `load()` never raises with zero
  plugins present).
- `tests/test_cli.py`: **8 new** — `plugin list`/`info`, empty
  discovery, unknown id, `disable` persisting across separate `main()`
  invocations (simulating separate processes), `enable` reporting the
  reload-needed message, `reload`, unknown-id error exit code, and a
  broken manifest never preventing the CLI from working.
- `tests/test_interactive.py`: **6 new** — `plugin list`/`info`,
  disable→list→enable→reload→list round trip within one session,
  unknown id, `plugin` with no subcommand, and plugin re-discovery
  after `use` switches `repository_root`.
- Full suite: **389 passed** (332 before this milestone + 43 + 8 + 6),
  no regressions.

## Real-World Verification

Before writing any test: created three real filesystem plugin
directories in scratch space — a working plugin, one with an
unparseable `plugin.json`, and one whose `initialize()` raises — and
ran the full CLI and REPL workflows against them (`plugin list/info/disable/enable/reload`),
confirming: the broken manifest is skipped without crashing discovery
(the bug above was caught exactly here), the broken-init plugin is
marked `failed` with its real error message while the good plugin
loads normally, disable state survives a fresh `PluginManager`
instance pointed at the same state file, and an intentional ID
conflict (the same plugin registered from two different directories)
is detected and isolated rather than silently overwriting. A stray
`.ocom/plugins/` directory this verification created inside the real
OCOM-Reader repository (already gitignored via `.ocom/`) was removed
afterward.

## Known Limitations

- **No dependency resolution between plugins** — explicitly out of
  scope per the task.
- **`config` has no real source yet** — the field exists on
  `PluginContext`, honestly empty, for a future milestone to populate.
- **REPL `plugin list` stays plain** (no color/table), consistent with
  M015's/M016's own deferred-scope decision for interactive rendering.
- **No sandboxing** — a plugin's Python code runs with the same
  privileges as the Reader process; nothing in this milestone was
  asked to change that, and nothing here claims otherwise.
- **`unload()`/`reload()` iterate all registered plugins when no id is
  given**, including ones already `failed` or never initialized —
  harmless (the loop skips anything not in `initialized`/`active`
  state) but worth naming as the actual behavior, not "all plugins are
  restarted."

## Roadmap

```
✅ M001-M016 — OCOM Reader MVP + Repository Independence + Better Retrieval + Rich CLI + Workspace (frozen)
✅ M017 Plugin Architecture — this document
⬜ M018 Web UI
⬜ M019 Optional LLM Layer
⬜ M020 Product Release
```
