"""CLI — thin argparse wrapper over Reader. No retrieval logic of its
own — every subcommand is one Reader call, formatted for display.

`search` and `related` print raw registry_ids (RetrievalMatch/RegistryEntry
are pointer-only — no title is resolved for them, the same way M007/M008
never resolved titles). `ask` and `explain` go through AnswerComposer,
the only place in this pipeline that resolves titles for presentation,
so their output is more readable. This asymmetry is deliberate, not an
oversight — see MILESTONE-009-010.md.

Bare `ocom-reader` (no subcommand) launches the interactive REPL
(M013, `interactive.py`) instead of erroring — every existing one-shot
invocation is otherwise unchanged.

M015: rich (colored, tabular, paged) output activates only on a real
terminal (`sys.stdout.isatty()`) — piped/redirected output (exactly
what every test and every script does) is byte-identical plain text to
before this milestone, unchanged. `--plain` forces the old behavior
even in a terminal; `NO_COLOR` (env) disables color only, leaving
tables/paging active. See MILESTONE-015-DESIGN.md.

M016: `repo add/list/use/remove` manage a name-to-path workspace
registry (`workspace/`), layered strictly above `Reader` — `cli.py`
only ever resolves a name to a path via `WorkspaceManager.resolve()`
and hands that path to the exact same `Reader(repository_root)` call
every prior milestone already uses. `--repo` still takes precedence
when passed explicitly; a user who never touches the workspace feature
sees no behavior change. See MILESTONE-016-DESIGN.md.

M017: `plugin list/info/enable/disable/reload` manage the plugin
infrastructure (`plugins/`) — pure bookkeeping over `PluginManager`,
never touching `RetrievalEngine`/`KnowledgeRegistry`/`Indexer`/`Composer`.
See MILESTONE-017-DESIGN.md.

M018: `web` starts the Web UI server (`web/`) — the browser is another
Reader client, not another implementation; `web/api.py` calls the same
`Reader`/`WorkspaceManager`/`PluginManager` this CLI already uses.
Binds to 127.0.0.1 by default. See MILESTONE-018-DESIGN.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from ocom_reader.cli_output import (
    maybe_page,
    render_ask_rich,
    render_completion_script,
    render_explain_rich,
    render_related_rich,
    render_search_rich,
    render_table,
    style,
    supports_color,
)
from ocom_reader.commands import run_ask, run_explain, run_related, run_search
from ocom_reader.interactive import run_interactive
from ocom_reader.llm import LLMAdapter, LLMConfig, LLMProviderName
from ocom_reader.plugins import PluginError, PluginManager
from ocom_reader.reader import Reader
from ocom_reader.vector_integration.loader import load_meetings, load_objects, load_statements, parse_frontmatter
from ocom_reader.vector_integration.models import KNOWN_SIGNALS, VectorStatement
from ocom_reader.vector_integration.navigation import (
    filter_to_current_meetings,
    find_object,
    render_cross_meeting_view,
    render_entity_timeline,
    render_mentions,
    render_object_view,
    render_relationship_tree,
)
from ocom_reader.vector_integration.promotion import render_promotion_review
from ocom_reader.vector_integration.query import search as vector_query_search
from ocom_reader.vector_integration.signals import (
    filter_by_signal,
    render_meeting_summary,
    render_signal_browser,
    render_statement,
)
from ocom_reader.vector_integration.stats import compute_stats, render_stats
from ocom_reader.web import DEFAULT_HOST, DEFAULT_PORT, start_server
from ocom_reader.workspace import WorkspaceError, WorkspaceManager

EPILOG = """\
Examples:
  ocom-reader ask "how does the retrieval engine rank results?"
  ocom-reader search registry
  ocom-reader related docs/architecture/MILESTONE-007.md
  ocom-reader explain "identity resolution"
  ocom-reader repo add ~/Projects/MyProject
  ocom-reader repo use MyProject
  ocom-reader vector show path/to/STM-....md          (Reader M01)
  ocom-reader vector search path/to/vector-repo --signal task
  ocom-reader vector object path/to/vector-repo PTN-20260727-A1NG   (Reader M03)
  ocom-reader vector mentioned-in path/to/vector-repo PTN-20260727-A1NG
  ocom-reader vector relationships path/to/vector-repo PTN-20260727-A1NG
  ocom-reader vector timeline path/to/vector-repo PTN-20260727-A1NG
  ocom-reader vector review path/to/vector-repo         (Reader M04)
  ocom-reader                      (interactive session)
  ocom-reader web                  (start the Web UI at http://127.0.0.1:8765)
  ocom-reader completion bash      (print a bash completion script)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocom-reader",
        description="Ask questions about a repository's documentation. "
        "Run with no command for an interactive session.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo", type=Path, default=None, help="Repository root to index (default: active workspace repo, else cwd)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip .ocom/ persistence — build in memory only, write nothing to disk",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Force plain, uncolored, non-tabular output even in a terminal",
    )
    parser.add_argument(
        "--workspace-file",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,  # override for tests; real usage always uses ~/.ocom_reader/workspace.json
    )
    parser.add_argument(
        "--plugin-state-file",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,  # override for tests; real usage always uses ~/.ocom_reader/plugins_state.json
    )
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,  # override for tests; real usage always uses ~/.ocom_reader/plugins
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    ask_parser = subparsers.add_parser("ask", help="Ask a question, get a composed answer")
    ask_parser.add_argument("query")
    ask_parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic"],
        default=None,
        help="Optionally rewrite the answer with an LLM (presentation only; API key from "
        "OPENAI_API_KEY/ANTHROPIC_API_KEY env var). Falls back silently to the "
        "deterministic answer if unavailable.",
    )

    search_parser = subparsers.add_parser("search", help="List ranked matching documents")
    search_parser.add_argument("query")

    related_parser = subparsers.add_parser("related", help="List documents directly related to a registry_id")
    related_parser.add_argument("registry_id")

    explain_parser = subparsers.add_parser("explain", help="Show found/related documents with reasons")
    explain_parser.add_argument("query")

    completion_parser = subparsers.add_parser("completion", help="Print a shell completion script")
    completion_parser.add_argument("shell", choices=["bash"], help="Shell to generate a completion script for")

    repo_parser = subparsers.add_parser("repo", help="Manage the multi-repository workspace")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command", required=True)

    repo_add = repo_subparsers.add_parser("add", help="Register a repository")
    repo_add.add_argument("path", type=Path)
    repo_add.add_argument("--name", help="Name to register under (default: directory name)")

    repo_subparsers.add_parser("list", help="List registered repositories")

    repo_use = repo_subparsers.add_parser("use", help="Set the active repository")
    repo_use.add_argument("name")

    repo_remove = repo_subparsers.add_parser("remove", help="Unregister a repository (never deletes its files)")
    repo_remove.add_argument("name")

    plugin_parser = subparsers.add_parser("plugin", help="Manage plugins")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command", required=True)

    plugin_subparsers.add_parser("list", help="List discovered plugins")

    plugin_info = plugin_subparsers.add_parser("info", help="Show details for one plugin")
    plugin_info.add_argument("id")

    plugin_enable = plugin_subparsers.add_parser("enable", help="Enable a plugin (persists across sessions)")
    plugin_enable.add_argument("id")

    plugin_disable = plugin_subparsers.add_parser("disable", help="Disable a plugin (persists across sessions)")
    plugin_disable.add_argument("id")

    plugin_reload = plugin_subparsers.add_parser("reload", help="Reload one plugin, or all if no id given")
    plugin_reload.add_argument("id", nargs="?")

    web_parser = subparsers.add_parser("web", help="Start the Web UI server")
    web_parser.add_argument("--host", default=DEFAULT_HOST, help=f"Interface to bind (default: {DEFAULT_HOST})")
    web_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind (default: {DEFAULT_PORT})")

    # Reader M01 — Contract Compliance (docs/contracts/vector-reader-contract.md).
    # Independent of Reader's own --repo/workspace machinery: a Vector repository
    # is a separate, external input, not "the repository being read" in Pipeline
    # A's sense — see vector_integration/ and READER_M01.md.
    vector_parser = subparsers.add_parser(
        "vector", help="Read Vector Statement/Meeting objects (vector-reader-contract.md)"
    )
    vector_subparsers = vector_parser.add_subparsers(dest="vector_command", required=True)

    vector_show = vector_subparsers.add_parser(
        "show", help="Display one Statement's Kind + Detected Signals"
    )
    vector_show.add_argument("path", type=Path, help="Path to a Vector Statement .md file")
    vector_show.add_argument(
        "--root", type=Path, default=None,
        help="Reader M03: a Vector repository root to resolve this Statement's "
             "references against, additionally printing a Mentions block",
    )

    # M02: search now takes an optional combinable `key:value` query
    # ("signal:task speaker:Denis meeting:XMFL") alongside M01's original
    # --signal flag, kept for backward compatibility with the M01 CLI.
    vector_search = vector_subparsers.add_parser(
        "search", help="Filter Statements — combinable signal:/speaker:/meeting: query"
    )
    vector_search.add_argument(
        "root", type=Path, help="Directory to search (a Vector objects/ or ai/staging/ tree)"
    )
    vector_search.add_argument(
        "query", nargs="?", default=None,
        help='Combinable filter query, e.g. "signal:task speaker:Denis meeting:XMFL" '
             "(see docs/vector-integration.md)",
    )
    vector_search.add_argument(
        "--signal", choices=sorted(KNOWN_SIGNALS), default=None,
        help="M01-compatible shorthand for a query of just 'signal:<value>' — omit if "
             "passing a query string",
    )

    vector_signals = vector_subparsers.add_parser(
        "signals", help="Signal Browser — every Statement grouped by signal"
    )
    vector_signals.add_argument("root", type=Path, help="Directory to browse")

    vector_summary = vector_subparsers.add_parser(
        "summary", help="Meeting Summary — signal counts for one Meeting's Statements"
    )
    vector_summary.add_argument("root", type=Path, help="A Meeting's directory")

    vector_stats = vector_subparsers.add_parser(
        "stats", help="Global Meeting/Statement/signal counts"
    )
    vector_stats.add_argument("root", type=Path, help="Directory to aggregate over")

    # Reader M03 — Object Navigation. Beyond vector-reader-contract.md v1.0's
    # stated (Statement-only) scope — see vector_integration/navigation.py's
    # module docstring and READER_M03.md.
    vector_object = vector_subparsers.add_parser(
        "object", help="Object View — type, name, linked Statements, meetings, aliases, relationships"
    )
    vector_object.add_argument("root", type=Path, help="Vector repository root (objects/ and/or ai/staging/)")
    vector_object.add_argument("object_id", help="Object id, e.g. PTN-20260727-A1NG")

    vector_mentioned_in = vector_subparsers.add_parser(
        "mentioned-in", help="Cross-Meeting View — every Meeting whose Statements mention this object"
    )
    vector_mentioned_in.add_argument("root", type=Path, help="Vector repository root")
    vector_mentioned_in.add_argument("object_id", help="Object id, e.g. PTN-20260727-A1NG")

    vector_relationships = vector_subparsers.add_parser(
        "relationships", help="Relationship Browser — text tree of this object's relationships"
    )
    vector_relationships.add_argument("root", type=Path, help="Vector repository root")
    vector_relationships.add_argument("object_id", help="Object id, e.g. PTN-20260727-A1NG")

    vector_timeline = vector_subparsers.add_parser(
        "timeline", help="Entity Timeline — mentions grouped by Meeting, sorted by meeting_date"
    )
    vector_timeline.add_argument("root", type=Path, help="Vector repository root")
    vector_timeline.add_argument("object_id", help="Object id, e.g. PTN-20260727-A1NG")

    # Reader M04 — Promotion Review UI (READER_M04_DESIGN.md). Deliberately
    # named "review", not "promotion" or "candidates" — Reader displays,
    # it never promotes or decides. Groups by the existing, single-valued
    # statement_kind field only; never a detected_signals combination.
    vector_review = vector_subparsers.add_parser(
        "review", help="Promotion Review — Statements grouped by statement_kind, for a human to review"
    )
    vector_review.add_argument("root", type=Path, help="Vector repository root")

    return parser


def _resolve_repo_path(args: argparse.Namespace, workspace: WorkspaceManager) -> Path:
    if args.repo is not None:
        return args.repo
    active = workspace.active()
    if active is not None:
        return Path(active.path)
    return Path(".")


def _run_vector_command(args: argparse.Namespace) -> int:
    """Reader M01 — Contract Compliance. Independent of --repo/workspace: a
    Vector repository is a separate, external input (see vector_integration/)."""
    if args.vector_command == "show":
        data = parse_frontmatter(args.path)
        if not data or data.get("type") != "statement":
            print(f"Error: {args.path} is not a Vector Statement object", file=sys.stderr)
            return 1
        try:
            stmt = VectorStatement.model_validate(data)
        except ValidationError as exc:
            print(f"Error: {args.path} does not satisfy vector-reader-contract.md: {exc}",
                  file=sys.stderr)
            return 1
        print(render_statement(stmt))
        if args.root is not None:
            objects = load_objects(args.root)
            print()
            print(render_mentions(stmt, objects))
        return 0

    if args.vector_command == "search":
        if args.query and args.signal:
            print(
                "Error: pass either a query string or --signal, not both "
                "(see docs/vector-integration.md)",
                file=sys.stderr,
            )
            return 1
        statements = load_statements(args.root)
        try:
            if args.query:
                matches = vector_query_search(statements, args.query)
            elif args.signal:
                matches = filter_by_signal(statements, args.signal)
            else:
                print("Error: pass a query string or --signal", file=sys.stderr)
                return 1
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if not matches:
            print("No Statements found")
            return 0
        for stmt in matches:
            print(f"[{stmt.id}] {stmt.title}")
        return 0

    if args.vector_command == "signals":
        statements = load_statements(args.root)
        print(render_signal_browser(statements))
        return 0

    if args.vector_command == "summary":
        statements = load_statements(args.root)
        print(render_meeting_summary(statements))
        return 0

    if args.vector_command == "stats":
        print(render_stats(compute_stats(args.root)))
        return 0

    if args.vector_command == "object":
        objects = load_objects(args.root)
        obj = find_object(objects, args.object_id)
        if obj is None:
            print(f"Error: no object {args.object_id!r} found under {args.root}", file=sys.stderr)
            return 1
        meetings = load_meetings(args.root)
        statements = filter_to_current_meetings(load_statements(args.root), meetings)
        print(render_object_view(obj, statements))
        return 0

    if args.vector_command == "mentioned-in":
        objects = load_objects(args.root)
        obj = find_object(objects, args.object_id)
        if obj is None:
            print(f"Error: no object {args.object_id!r} found under {args.root}", file=sys.stderr)
            return 1
        meetings = load_meetings(args.root)
        statements = filter_to_current_meetings(load_statements(args.root), meetings)
        print(render_cross_meeting_view(obj, statements, meetings))
        return 0

    if args.vector_command == "relationships":
        objects = load_objects(args.root)
        obj = find_object(objects, args.object_id)
        if obj is None:
            print(f"Error: no object {args.object_id!r} found under {args.root}", file=sys.stderr)
            return 1
        print(render_relationship_tree(obj, objects))
        return 0

    if args.vector_command == "timeline":
        objects = load_objects(args.root)
        obj = find_object(objects, args.object_id)
        if obj is None:
            print(f"Error: no object {args.object_id!r} found under {args.root}", file=sys.stderr)
            return 1
        meetings = load_meetings(args.root)
        statements = filter_to_current_meetings(load_statements(args.root), meetings)
        print(render_entity_timeline(obj, statements, meetings))
        return 0

    if args.vector_command == "review":
        meetings = load_meetings(args.root)
        statements = filter_to_current_meetings(load_statements(args.root), meetings)
        print(render_promotion_review(statements, meetings))
        return 0

    return 1  # pragma: no cover — argparse enforces the choices set above


def _run_repo_command(args: argparse.Namespace, workspace: WorkspaceManager, rich: bool, color: bool) -> str:
    if args.repo_command == "add":
        name = args.name or Path(args.path).expanduser().resolve().name
        entry = workspace.add(name, args.path)
        return f"Registered {entry.name!r} -> {entry.path}"

    if args.repo_command == "list":
        entries = workspace.list()
        if not entries:
            return "No repositories registered. Use 'repo add <path>'."
        active_name = workspace.active().name if workspace.active() else None
        rows = [
            [
                e.name,
                e.path,
                "*" if e.name == active_name else "",
                "yes" if workspace.is_initialized(e.name) else "no",
            ]
            for e in entries
        ]
        if rich:
            return render_table(["name", "path", "active", "initialized"], rows, color=color)
        lines = ["Registered repositories:"]
        lines.extend(f"  - {r[0]} ({r[1]}) active={r[2] == '*'} initialized={r[3]}" for r in rows)
        return "\n".join(lines)

    if args.repo_command == "use":
        entry = workspace.use(args.name)
        return f"Active repository: {entry.name!r} ({entry.path})"

    if args.repo_command == "remove":
        workspace.remove(args.name)
        return f"Removed {args.name!r} from the workspace (its files were not touched)."

    return "Unknown repo command."  # pragma: no cover — argparse enforces the choices set above


def _build_plugin_manager(args: argparse.Namespace, repo_path: Path) -> PluginManager:
    kwargs = {}
    if args.plugin_state_file is not None:
        kwargs["state_path"] = args.plugin_state_file
    if args.plugin_dir is not None:
        kwargs["user_plugin_dir"] = args.plugin_dir
    manager = PluginManager(repository_root=repo_path, **kwargs)
    manager.load()
    return manager


def _run_plugin_command(args: argparse.Namespace, manager: PluginManager, rich: bool, color: bool) -> str:
    if args.plugin_command == "list":
        records = manager.plugins()
        if not records:
            return "No plugins discovered."
        rows = [
            [
                r.manifest.id,
                r.manifest.name,
                r.manifest.version,
                r.state.value,
                "yes" if r.enabled else "no",
            ]
            for r in records
        ]
        if rich:
            return render_table(["id", "name", "version", "state", "enabled"], rows, color=color)
        lines = ["Discovered plugins:"]
        lines.extend(f"  - {r[0]} ({r[1]} v{r[2]}) state={r[3]} enabled={r[4]}" for r in rows)
        return "\n".join(lines)

    if args.plugin_command == "info":
        record = manager.plugin(args.id)
        if record is None:
            return f"No plugin with id {args.id!r}."
        m = record.manifest
        return (
            f"{m.id} — {m.name} v{m.version}\n"
            f"  author: {m.author}\n"
            f"  description: {m.description}\n"
            f"  entry_point: {m.entry_point}\n"
            f"  minimum_reader_version: {m.minimum_reader_version}\n"
            f"  source: {record.source}\n"
            f"  state: {record.state.value}\n"
            f"  enabled: {record.enabled}\n"
            f"  error: {record.error or '(none)'}"
        )

    if args.plugin_command == "enable":
        manager.enable(args.id)
        return f"Enabled {args.id!r}. Reload to activate it in this session."

    if args.plugin_command == "disable":
        manager.disable(args.id)
        return f"Disabled {args.id!r}."

    if args.plugin_command == "reload":
        manager.reload(args.id)
        return f"Reloaded {args.id!r}." if args.id else "Reloaded all plugins."

    return "Unknown plugin command."  # pragma: no cover — argparse enforces the choices set above


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "completion":
        print(render_completion_script(args.shell))
        return 0

    if args.command == "vector":
        return _run_vector_command(args)

    is_tty = sys.stdout.isatty()
    rich = is_tty and not args.plain
    color = supports_color(no_color_flag=args.plain)
    # Paging additionally requires stdin to be a real, interactive
    # terminal with a usable TERM — pydoc.pager() can otherwise hang
    # waiting for a keypress that will never come. Reproduced during
    # M015's own real-terminal verification: even with stdin/stdout
    # both reporting isatty()=True, an environment with TERM unset (or
    # "dumb") has no real interactive pager available, and pydoc falls
    # back to a "press RETURN" prompt that hangs forever with no real
    # user able to respond. See MILESTONE-015.md.
    term = os.environ.get("TERM")
    can_page = rich and sys.stdin.isatty() and term not in (None, "", "dumb")

    workspace = WorkspaceManager(state_path=args.workspace_file)

    if args.command == "repo":
        try:
            print(_run_repo_command(args, workspace, rich, color))
            return 0
        except WorkspaceError as exc:
            print(style(f"Error: {exc}", "yellow", color=color))
            return 1

    if args.command == "plugin":
        try:
            repo_path = _resolve_repo_path(args, workspace)
            manager = _build_plugin_manager(args, repo_path)
            print(_run_plugin_command(args, manager, rich, color))
            return 0
        except (WorkspaceError, PluginError) as exc:
            print(style(f"Error: {exc}", "yellow", color=color))
            return 1

    if args.command == "web":
        try:
            repo_path = _resolve_repo_path(args, workspace)
        except WorkspaceError as exc:
            print(style(f"Error: {exc}", "yellow", color=color))
            return 1
        server = start_server(
            host=args.host,
            port=args.port,
            repository_root=repo_path,
            workspace_state_path=args.workspace_file,
            use_persistence=not args.no_cache,
            plugin_state_path=args.plugin_state_file,
            plugin_dir=args.plugin_dir,
        )
        print(f"OCOM Reader Web UI running at http://{args.host}:{args.port}/ (Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0

    if args.command is None:
        try:
            repo_path = _resolve_repo_path(args, workspace)
        except WorkspaceError as exc:
            print(style(f"Error: {exc}", "yellow", color=color))
            return 1
        return run_interactive(
            repo_path,
            use_persistence=not args.no_cache,
            workspace_state_path=args.workspace_file,
            plugin_state_path=args.plugin_state_file,
            plugin_dir=args.plugin_dir,
        )

    try:
        repo_path = _resolve_repo_path(args, workspace)
    except WorkspaceError as exc:
        print(style(f"Error: {exc}", "yellow", color=color))
        return 1

    reader = Reader(repo_path, use_persistence=not args.no_cache)

    if args.command == "ask":
        answer = reader.answer(args.query)
        output = render_ask_rich(answer, color=color) if rich else run_ask(reader, args.query)

        if args.llm_provider:
            llm_config = LLMConfig(provider=LLMProviderName(args.llm_provider))
            llm_result = LLMAdapter(llm_config).enhance(answer)
            if llm_result.succeeded:
                header = style("Natural Language Answer", "bold", "cyan", color=color)
                output = f"{output}\n\n{header}\n  {llm_result.text}"
            else:
                note = style(
                    f"(LLM unavailable: {llm_result.fallback_reason} — showing deterministic answer only)",
                    "dim",
                    color=color,
                )
                output = f"{output}\n\n{note}"

        maybe_page(output, enabled=can_page)
        return 0
    elif args.command == "search":
        matches = reader.search(args.query)
        output = render_search_rich(matches, args.query, color=color) if rich else run_search(reader, args.query)
    elif args.command == "related":
        entries = reader.related(args.registry_id)
        output = (
            render_related_rich(entries, args.registry_id, color=color)
            if rich
            else run_related(reader, args.registry_id)
        )
    elif args.command == "explain":
        documents = reader.explain(args.query)
        output = render_explain_rich(documents, args.query, color=color) if rich else run_explain(reader, args.query)
    else:  # pragma: no cover — argparse enforces the choices set above
        return 2

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
