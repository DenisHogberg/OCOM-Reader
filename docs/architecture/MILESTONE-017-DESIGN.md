# MILESTONE-017: Plugin Architecture — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation per the established workflow.
**Builds on:** [MILESTONE-016](MILESTONE-016.md), [MILESTONE-012](MILESTONE-012.md)

## Objective

Infrastructure through which Reader can be extended without changing
its core — not a single concrete plugin. After this milestone, any new
extension connects through the Plugin API, not by editing existing
components. Explicitly out of scope (future milestones): AI Provider,
Markdown/PDF/HTML export, Search Provider, remote plugins, a
marketplace, auto-updates, dependency resolution between plugins.

## The One Rule

The plugin layer **never imports** `RetrievalEngine`, `KnowledgeRegistry`,
`Indexer`, or `Composer` — not in `plugins/`, and a plugin itself never
receives them. A plugin only ever sees `PluginContext`, a small,
explicitly-safe surface. This is checked mechanically before the final
report (`grep` across `plugins/` for those four names), not just
claimed.

## Package Structure

```
plugins/
    __init__.py
    protocol.py     Plugin (Protocol), PluginManifest, Capability, PluginState
    context.py       PluginContext, PluginWorkspaceView
    exceptions.py    PluginError hierarchy
    registry.py      PluginRegistry — registration, lookup, ID conflicts, compatibility
    loader.py         PluginLoader — discovery + instantiation only, no lifecycle/business logic
    manager.py        PluginManager — orchestrates load/unload/reload, owns error isolation
    builtin/
        __init__.py   BUILTIN_PLUGINS = [] — the discovery mechanism is real; nothing ships in it
```

## Plugin Protocol

`typing.Protocol` (not ABC) — structural typing, so a plugin author
never has to import an OCOM Reader base class to implement one,
`@runtime_checkable` so the loader can `isinstance()`-validate a
loaded object actually satisfies the shape before treating it as a
plugin.

```python
@runtime_checkable
class Plugin(Protocol):
    id: str
    name: str
    version: str
    description: str
    def initialize(self, context: PluginContext) -> None: ...
    def shutdown(self) -> None: ...
    def capabilities(self) -> list[Capability]: ...
```

```python
class Capability(str, Enum):
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    INDEXER = "INDEXER"
    RENDERER = "RENDERER"
    COMMAND = "COMMAND"
    AI_PROVIDER = "AI_PROVIDER"
    UTILITY = "UTILITY"
```

## Plugin Manifest

```python
class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    author: str
    description: str
    entry_point: str              # "module:ClassName"
    minimum_reader_version: str
```

Capabilities are **not** part of the manifest — they come from calling
`.capabilities()` on the *loaded instance*, per the task's own Plugin
Protocol sketch. A manifest describes identity and compatibility; a
loaded plugin describes what it can do.

`entry_point` format: `"<module>:<ClassName>"`. For a filesystem
plugin, `<module>` is loaded from that plugin's own `plugin.py` via
`importlib.util.spec_from_file_location` — each plugin gets its own
isolated module namespace, so two unrelated plugins can each have a
file named `plugin.py` without colliding.

## Plugin Context — the only thing a plugin ever sees

```python
@dataclass(frozen=True)
class PluginWorkspaceView:
    active_repository: Optional[str]
    repositories: list[str]

@dataclass(frozen=True)
class PluginContext:
    repository_root: Path
    workspace: PluginWorkspaceView
    config: dict
    logger: logging.Logger
    reader_version: str
```

`workspace` is a frozen **snapshot**, not a reference to the real
`WorkspaceManager` — it has no `add`/`use`/`remove` methods to call,
structurally, not just by convention. `config` is an empty `dict` for
now (a real per-plugin configuration source wasn't asked for beyond
the field existing) — a grounded placeholder for future extension, the
same honest-placeholder discipline M012's `retrieval.json` used.
`logger` is `logging.getLogger(f"ocom_reader.plugins.{plugin_id}")`,
namespaced per plugin. `reader_version` from
`importlib.metadata.version("ocom-reader")`, never hardcoded — same as
`persistence.store.StorageMetadata`.

## Discovery (order is a contract, documented here explicitly)

1. **builtin** — `PluginManager`'s injected `builtin_plugins: list[type]`
   (production default: empty list from `plugins.builtin.BUILTIN_PLUGINS`).
2. **user** — `~/.ocom_reader/plugins/*/`, each a `plugin.json` + `plugin.py` directory.
3. **repository-local** — `<repository_root>/.ocom/plugins/*/`, same shape.

Later sources are discovered after earlier ones, but IDs are **not**
allowed to silently override — `PluginRegistry.register()` raises
`PluginConflictError` on a duplicate ID regardless of source order.
The order only determines *which* registration wins the slot (first
discovered) and therefore what the conflict error can report ("already
registered from builtin", etc.) — it is not a precedence/override
mechanism.

## Lifecycle

```
discovered → loaded → initialized → active
                │            │
                └──────┴──→ failed
active/initialized → unloaded (shutdown() called)
```

- **discovered**: a manifest was found and parsed (loader's job).
- **loaded**: `PluginRegistry.register()` succeeded and the entry_point
  class was imported and instantiated (still no `initialize()` call yet).
- **initialized**: `initialize(context)` returned without raising.
- **active**: initialized **and** enabled — the state a plugin needs
  to be in for `plugins_by_capability()` to consider it. A disabled
  plugin can sit at `initialized` (loaded and ready, just not switched
  on) without ever reaching `active`.
- **failed**: any step raised. The manifest's own error message is
  preserved on the record (`PluginRecord.error`).
- **unloaded**: `shutdown()` was called (explicit `unload()`, or the
  first half of `reload()`).

## Error Isolation

`PluginLoader`/`PluginRegistry` raise honest, specific exceptions for
a single unit of work — they never swallow errors ("Loader отвечает
только за загрузку. Никакой бизнес-логики"). `PluginManager.load()`
is the **one** place that catches per-plugin, logs, marks that record
`failed`, and continues to the next discovered plugin — one plugin's
`ImportError`/`initialize()` exception/malformed `plugin.json` never
stops the others from loading. This is proven with a real, deliberately
broken plugin directory in the real-plugin verification pass below,
not only asserted in a mocked unit test.

## Enable/Disable Persistence

`enable`/`disable` need to survive process exit to be useful as
one-shot CLI commands (`ocom-reader plugin disable X` followed by a
*later*, separate `ocom-reader ask ...` invocation) — the same
reasoning M016 already established for `repo use`. A small, versioned
file, `~/.ocom_reader/plugins_state.json` (`{"version": 1, "disabled": ["id", ...]}`),
overridable via constructor for tests exactly like `WorkspaceManager`'s
`state_path`. `PluginManager.load()` consults it before initializing
each discovered plugin — a disabled plugin still gets registered and
loaded (so `plugin info` can describe it), just never initialized,
staying at `loaded`.

## Registry Responsibilities

`PluginRegistry` owns: registration (raises `PluginConflictError` on
duplicate ID), lookup by ID, listing all records, and compatibility
checking (`minimum_reader_version` vs. the installed reader version —
simple tuple comparison of dotted version strings, no new dependency).
It does **not** import or instantiate anything — `PluginManager` and
`PluginLoader` do that; the registry only tracks manifests and state.

## Manager Responsibilities

`PluginManager` is the one orchestrator: `load()` (discover all three
sources, register, instantiate, initialize-unless-disabled, isolating
failures), `unload(plugin_id=None)` (call `shutdown()` on one or all
active/initialized plugins), `reload(plugin_id=None)` (unload then
load again), `plugins()`/`plugin(id)`/`enabled_plugins()`/`disabled_plugins()`
(pure queries over the registry), `plugins_by_capability(capability)`
(filters `active` plugins by their live `.capabilities()` call).

## CLI / Interactive

```bash
ocom-reader plugin list
ocom-reader plugin info <id>
ocom-reader plugin enable <id>
ocom-reader plugin disable <id>
ocom-reader plugin reload [id]
```

Same four verbs as REPL commands (`plugin list/info/enable/disable/reload`),
mirroring M016's `repo` command pattern exactly. `plugin list` uses
`cli_output.render_table` in rich mode (columns: `id | name | version |
state | enabled | capabilities`), plain listing otherwise — same
TTY-gated discipline as every prior CLI output.

## Test Plan

Registration, load, unload, ID conflict, reload, invalid manifest,
`initialize()` raising, `shutdown()` raising, capability lookup,
disabled-plugin skip, filesystem discovery (a real plugin directory
written to `tmp_path`, not mocked), builtin discovery (an injected fake
builtin class), CLI, REPL. Real-plugin verification (a working
filesystem plugin *and* a deliberately broken one in the same
directory, proving isolation) runs before any test is written, the
same discipline used for every prior milestone's real-repository pass
— here a real *plugin*, since this milestone's subject is plugins, not
retrieval.

## Architectural Confirmation (to re-verify, not just plan, before the final report)

`git diff --stat` against `retrieval/`, `registry/`, `indexer/`,
`composer/` must be empty. `grep -rn "RetrievalEngine\|KnowledgeRegistry\|RepositoryIndexBuilder\|AnswerComposer" src/ocom_reader/plugins/`
must return nothing.

Proceeding to implementation now.
