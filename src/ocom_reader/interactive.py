"""Interactive CLI (M013) — bare `ocom-reader` launches a REPL.

`read_line`/`write` are injected (default to real `input`/`print`) so
the loop is testable without a real TTY: tests pass a fake `read_line`
that pops from a predetermined command list and raises `EOFError` when
exhausted, matching real `input()`'s end-of-stream behavior.

"Context switching" (the task's own term) started narrow in M013: an
in-session `use <path>` command that points the session at a different
repository by path, no naming. M016 adds `repo add/list/use/remove`
alongside it — named, persistent, workspace-backed switching — without
changing `use <path>`'s own behavior. Per M015's own scope decision,
`repo list` here stays plain (no color/table) — REPL rich rendering
remains deferred, not silently expanded.

M017 adds `plugin list/info/enable/disable/reload`, backed by the same
`PluginManager` the CLI uses — loaded once per session (or `use`/`repo use`
switch, since plugins are discovered per repository_root).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Callable, Optional

from ocom_reader.commands import run_ask, run_explain, run_related, run_search
from ocom_reader.plugins import PluginError, PluginManager
from ocom_reader.reader import Reader
from ocom_reader.workspace import WorkspaceError, WorkspaceManager

try:
    import readline  # noqa: F401  — enables real-terminal up-arrow recall via input(); no effect on piped stdin.
except ImportError:  # pragma: no cover - platform-dependent (e.g. some Windows setups)
    pass

WELCOME = "OCOM Reader interactive session. Type 'help' for commands, 'exit' to quit."
GOODBYE = "Goodbye."
HELP_TEXT = """Commands:
  ask <query>              Ask a question, get a composed answer
                             e.g. ask how does retrieval ranking work
  search <query>            List ranked matching documents
                             e.g. search registry
  related <registry_id>     List documents directly related to a registry_id
                             e.g. related docs/architecture/MILESTONE-007.md
  explain <query>           Show found/related documents with reasons
                             e.g. explain identity resolution
  use <path>                 Switch the active repository (unregistered, this session only)
                             e.g. use ../another-project
  repo add <path> [name]     Register a repository in the workspace
                             e.g. repo add ~/Projects/MyProject
  repo list                  List registered repositories
  repo use <name>             Switch to a registered repository by name
  repo remove <name>          Unregister a repository (never deletes its files)
  plugin list                 List discovered plugins
  plugin info <id>             Show details for one plugin
  plugin enable <id>            Enable a plugin (persists across sessions)
  plugin disable <id>           Disable a plugin (persists across sessions)
  plugin reload [id]            Reload one plugin, or all if no id given
  history                    List commands entered this session
  help                       Show this message
  exit, quit                 Leave the session"""


class InteractiveSession:
    def __init__(
        self,
        repository_root: Path,
        use_persistence: bool = True,
        workspace_state_path: Optional[Path] = None,
        plugin_state_path: Optional[Path] = None,
        plugin_dir: Optional[Path] = None,
    ) -> None:
        self._use_persistence = use_persistence
        self._repository_root = Path(repository_root)
        self.reader = Reader(self._repository_root, use_persistence=use_persistence)
        self.history: list[str] = []
        self._workspace = WorkspaceManager(state_path=workspace_state_path)
        self._plugin_state_path = plugin_state_path
        self._plugin_dir = plugin_dir
        self._plugins: Optional[PluginManager] = None

    @property
    def repository_root(self) -> Path:
        return self._repository_root

    def dispatch(self, line: str) -> str:
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return f"Could not parse command: {exc}"

        if not parts:
            return ""

        command, args = parts[0], parts[1:]

        if command == "help":
            return HELP_TEXT
        if command == "history":
            return self._render_history()
        if command == "use":
            return self._use(args)
        if command == "repo":
            return self._repo(args)
        if command == "plugin":
            return self._plugin(args)
        if command == "ask":
            return run_ask(self.reader, " ".join(args)) if args else "Usage: ask <query>"
        if command == "search":
            return run_search(self.reader, " ".join(args)) if args else "Usage: search <query>"
        if command == "related":
            return run_related(self.reader, args[0]) if args else "Usage: related <registry_id>"
        if command == "explain":
            return run_explain(self.reader, " ".join(args)) if args else "Usage: explain <query>"

        return f"Unknown command: {command!r}. Type 'help' for a list of commands."

    def _use(self, args: list[str]) -> str:
        if not args:
            return "Usage: use <repository_path>"
        new_root = Path(args[0]).expanduser()
        if not new_root.is_dir():
            return f"Not a directory: {new_root}"
        self.reader = Reader(new_root, use_persistence=self._use_persistence)
        self._repository_root = new_root
        self._plugins = None  # re-discover plugins for the new repository_root on next use
        return f"Switched to repository: {new_root.resolve()}"

    def _repo(self, args: list[str]) -> str:
        if not args:
            return "Usage: repo <add|list|use|remove> ..."
        sub, rest = args[0], args[1:]

        try:
            if sub == "add":
                if not rest:
                    return "Usage: repo add <path> [name]"
                path = Path(rest[0])
                name = rest[1] if len(rest) > 1 else path.expanduser().resolve().name
                entry = self._workspace.add(name, path)
                return f"Registered {entry.name!r} -> {entry.path}"
            if sub == "list":
                entries = self._workspace.list()
                if not entries:
                    return "No repositories registered. Use 'repo add <path>'."
                active_name = self._workspace.active().name if self._workspace.active() else None
                lines = ["Registered repositories:"]
                for e in entries:
                    marker = "*" if e.name == active_name else " "
                    initialized = "yes" if self._workspace.is_initialized(e.name) else "no"
                    lines.append(f"  {marker} {e.name} ({e.path}) initialized={initialized}")
                return "\n".join(lines)
            if sub == "use":
                if not rest:
                    return "Usage: repo use <name>"
                entry = self._workspace.use(rest[0])
                self.reader = Reader(Path(entry.path), use_persistence=self._use_persistence)
                self._repository_root = Path(entry.path)
                self._plugins = None  # re-discover plugins for the new repository_root on next use
                return f"Active repository: {entry.name!r} ({entry.path})"
            if sub == "remove":
                if not rest:
                    return "Usage: repo remove <name>"
                self._workspace.remove(rest[0])
                return f"Removed {rest[0]!r} from the workspace (its files were not touched)."
            return f"Unknown repo command: {sub!r}. Try add, list, use, or remove."
        except WorkspaceError as exc:
            return f"Error: {exc}"

    def _plugin_manager(self) -> PluginManager:
        if self._plugins is None:
            kwargs = {}
            if self._plugin_state_path is not None:
                kwargs["state_path"] = self._plugin_state_path
            if self._plugin_dir is not None:
                kwargs["user_plugin_dir"] = self._plugin_dir
            self._plugins = PluginManager(repository_root=self._repository_root, **kwargs)
            self._plugins.load()
        return self._plugins

    def _plugin(self, args: list[str]) -> str:
        if not args:
            return "Usage: plugin <list|info|enable|disable|reload> ..."
        sub, rest = args[0], args[1:]
        manager = self._plugin_manager()

        try:
            if sub == "list":
                records = manager.plugins()
                if not records:
                    return "No plugins discovered."
                lines = ["Discovered plugins:"]
                lines.extend(
                    f"  - {r.manifest.id} ({r.manifest.name} v{r.manifest.version}) "
                    f"state={r.state.value} enabled={r.enabled}"
                    for r in records
                )
                return "\n".join(lines)
            if sub == "info":
                if not rest:
                    return "Usage: plugin info <id>"
                record = manager.plugin(rest[0])
                if record is None:
                    return f"No plugin with id {rest[0]!r}."
                m = record.manifest
                return (
                    f"{m.id} — {m.name} v{m.version}\n"
                    f"  author: {m.author}\n"
                    f"  description: {m.description}\n"
                    f"  source: {record.source}\n"
                    f"  state: {record.state.value}\n"
                    f"  enabled: {record.enabled}\n"
                    f"  error: {record.error or '(none)'}"
                )
            if sub == "enable":
                if not rest:
                    return "Usage: plugin enable <id>"
                manager.enable(rest[0])
                return f"Enabled {rest[0]!r}. Reload to activate it in this session."
            if sub == "disable":
                if not rest:
                    return "Usage: plugin disable <id>"
                manager.disable(rest[0])
                return f"Disabled {rest[0]!r}."
            if sub == "reload":
                plugin_id = rest[0] if rest else None
                manager.reload(plugin_id)
                return f"Reloaded {plugin_id!r}." if plugin_id else "Reloaded all plugins."
            return f"Unknown plugin command: {sub!r}. Try list, info, enable, disable, or reload."
        except PluginError as exc:
            return f"Error: {exc}"

    def _render_history(self) -> str:
        if not self.history:
            return "(empty)"
        return "\n".join(f"  {i}. {cmd}" for i, cmd in enumerate(self.history, start=1))


def run_interactive(
    repository_root: Path,
    use_persistence: bool = True,
    read_line: Optional[Callable[[str], str]] = None,
    write: Callable[[str], None] = print,
    workspace_state_path: Optional[Path] = None,
    plugin_state_path: Optional[Path] = None,
    plugin_dir: Optional[Path] = None,
) -> int:
    if read_line is None:
        read_line = input  # resolved at call time, not def time, so tests can monkeypatch builtins.input
    session = InteractiveSession(
        repository_root,
        use_persistence=use_persistence,
        workspace_state_path=workspace_state_path,
        plugin_state_path=plugin_state_path,
        plugin_dir=plugin_dir,
    )
    write(WELCOME)

    while True:
        prompt = f"ocom-reader [{session.repository_root.resolve().name}]> "
        try:
            line = read_line(prompt)
        except EOFError:
            write("")
            write(GOODBYE)
            return 0
        except KeyboardInterrupt:
            write("")
            continue

        line = line.strip()
        if not line:
            continue

        session.history.append(line)

        if line in ("exit", "quit"):
            write(GOODBYE)
            return 0

        try:
            output = session.dispatch(line)
        except Exception as exc:  # a bad command must never kill the session
            output = f"Error: {exc}"

        if output:
            write(output)
