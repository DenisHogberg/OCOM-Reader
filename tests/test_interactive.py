"""Interactive CLI (M013).

`InteractiveSession.dispatch()` is tested directly (no I/O). `run_interactive()`
is tested with an injected `read_line`/`write` pair driving a scripted
session — no real TTY needed. A dedicated real-repository section
(bottom) drives a scripted session against this project's own
repository, plus a real subprocess with piped stdin proving the actual
terminal-facing entry points behave the same way.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ocom_reader.interactive import InteractiveSession, run_interactive


def _write_test_plugin(directory: Path, plugin_id: str) -> None:
    plugin_dir = directory / plugin_id.replace("-", "_")
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
                "name": plugin_id.title(),
                "version": "1.0.0",
                "author": "Test",
                "description": "d",
                "entry_point": "plugin:TestPlugin",
                "minimum_reader_version": "0.1.0",
            }
        )
    )
    (plugin_dir / "plugin.py").write_text(
        f"""
class TestPlugin:
    id = {plugin_id!r}
    name = {plugin_id.title()!r}
    version = "1.0.0"
    description = "d"
    def initialize(self, context):
        pass
    def shutdown(self):
        pass
    def capabilities(self):
        return []
"""
    )


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WorkspaceManager (M016) defaults to ~/.ocom_reader/workspace.json
    — every test in this module must never touch the real home
    directory. A sibling of tmp_path, not a subdirectory, so it never
    ends up inside a repository fixture that indexes tmp_path itself."""
    fake_home = tmp_path.parent / f"{tmp_path.name}-home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(tmp_path, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\nBody.")
    return tmp_path


def _scripted(commands: list[str]):
    remaining = iter(commands)

    def read_line(prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError

    return read_line


# --- InteractiveSession.dispatch() ---------------------------------------------


def test_dispatch_ask(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("ask runtime")

    assert "Question: runtime" in output


def test_dispatch_ask_with_quoted_multiword_query(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch('ask "how does runtime work"')

    assert "Question: how does runtime work" in output


def test_dispatch_search(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("search runtime")

    assert "docs/architecture/ADR-001-runtime.md" in output


def test_dispatch_related(repo: Path) -> None:
    # ADR-001/ADR-002 are consecutively numbered, so they pick up an
    # architecture_sequence relation automatically (M007) — a real
    # related() result, not an empty one.
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("related docs/architecture/ADR-001-runtime.md")

    assert "docs/architecture/ADR-002-evidence.md" in output


def test_dispatch_explain(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("explain runtime")

    assert "Title match: runtime" in output


def test_dispatch_help(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("help")

    assert "ask <query>" in output
    assert "use <path>" in output


def test_dispatch_unknown_command(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("frobnicate")

    assert "Unknown command" in output


def test_dispatch_empty_line_is_a_noop(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("") == ""
    assert session.dispatch("   ") == ""


def test_dispatch_command_missing_required_argument(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("ask") == "Usage: ask <query>"
    assert session.dispatch("related") == "Usage: related <registry_id>"


def test_dispatch_malformed_quoting_does_not_raise(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch('ask "unterminated')

    assert "Could not parse command" in output


# --- Context switching (use) --------------------------------------------------


def test_use_switches_the_active_repository(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other_repo"
    _write(other, "docs/architecture/ADR-001-search.md", "# Search\n\nBody.")
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch(f"use {other}")

    assert "Switched to repository" in output
    assert session.repository_root == other
    assert "Search" in session.dispatch("ask search").split("Most relevant:")[1]


def test_use_with_no_argument_is_a_usage_error(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("use") == "Usage: use <repository_path>"


def test_use_with_a_nonexistent_path_does_not_switch(repo: Path, tmp_path: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)
    original_root = session.repository_root

    output = session.dispatch(f"use {tmp_path / 'does-not-exist'}")

    assert "Not a directory" in output
    assert session.repository_root == original_root


# --- Multi-Repository Workspace (M016) -----------------------------------


def test_repo_add_and_list(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    _write(other, "docs/architecture/ADR-001-other.md", "# Other\n\nBody.")
    session = InteractiveSession(repo, use_persistence=False)

    session.dispatch(f"repo add {other} beta")
    output = session.dispatch("repo list")

    assert "beta" in output
    assert str(other) in output


def test_repo_use_switches_the_reader(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    _write(other, "docs/architecture/ADR-001-other.md", "# Other Concept\n\nBody.")
    session = InteractiveSession(repo, use_persistence=False)
    session.dispatch(f"repo add {other} beta")

    output = session.dispatch("repo use beta")

    assert "beta" in output
    assert session.repository_root == other
    answer_output = session.dispatch("ask other")
    assert "Question: other" in answer_output


def test_repo_remove_never_deletes_files(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    _write(other, "docs/architecture/ADR-001-other.md", "# Other\n\nBody.")
    session = InteractiveSession(repo, use_persistence=False)
    session.dispatch(f"repo add {other} beta")

    session.dispatch("repo remove beta")

    assert other.exists()
    assert list(other.rglob("*.md"))


def test_repo_use_unknown_name_reports_an_error(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    output = session.dispatch("repo use nope")

    assert "Error" in output


def test_repo_with_no_subcommand_is_a_usage_error(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("repo") == "Usage: repo <add|list|use|remove> ..."


def test_repo_list_with_nothing_registered(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert "No repositories registered" in session.dispatch("repo list")


# --- Plugin Architecture (M017) -------------------------------------------


def test_plugin_list_and_info(repo: Path, tmp_path: Path) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")
    session = InteractiveSession(
        repo, use_persistence=False, plugin_dir=tmp_path / "plugins", plugin_state_path=tmp_path / "state.json"
    )

    list_output = session.dispatch("plugin list")
    info_output = session.dispatch("plugin info alpha")

    assert "alpha" in list_output
    assert "state: active" in info_output


def test_plugin_list_with_nothing_discovered(repo: Path, tmp_path: Path) -> None:
    session = InteractiveSession(
        repo, use_persistence=False, plugin_dir=tmp_path / "empty", plugin_state_path=tmp_path / "state.json"
    )

    assert "No plugins discovered" in session.dispatch("plugin list")


def test_plugin_disable_then_enable_and_reload(repo: Path, tmp_path: Path) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")
    session = InteractiveSession(
        repo, use_persistence=False, plugin_dir=tmp_path / "plugins", plugin_state_path=tmp_path / "state.json"
    )
    session.dispatch("plugin list")  # triggers first load

    disable_output = session.dispatch("plugin disable alpha")
    after_disable = session.dispatch("plugin list")

    assert "Disabled" in disable_output
    assert "enabled=False" in after_disable

    session.dispatch("plugin enable alpha")
    session.dispatch("plugin reload")
    after_reload = session.dispatch("plugin list")

    assert "state=active" in after_reload


def test_plugin_info_unknown_id(repo: Path, tmp_path: Path) -> None:
    session = InteractiveSession(
        repo, use_persistence=False, plugin_dir=tmp_path / "empty", plugin_state_path=tmp_path / "state.json"
    )

    assert "No plugin with id" in session.dispatch("plugin info nope")


def test_plugin_with_no_subcommand_is_a_usage_error(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("plugin") == "Usage: plugin <list|info|enable|disable|reload> ..."


def test_plugins_are_rediscovered_after_switching_repository(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other_repo"
    _write(other, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    _write_test_plugin(tmp_path / "plugins_a", "alpha")
    _write_test_plugin(tmp_path / "plugins_b", "beta")
    session = InteractiveSession(
        repo, use_persistence=False, plugin_dir=tmp_path / "plugins_a", plugin_state_path=tmp_path / "state.json"
    )
    first_list = session.dispatch("plugin list")

    session.dispatch(f"use {other}")
    # plugin_dir stays user-level in this session's config; what changes
    # is repository_root, so repository-local .ocom/plugins/ would differ
    # — re-triggering discovery must not raise even though nothing new
    # is found there.
    second_list = session.dispatch("plugin list")

    assert "alpha" in first_list
    assert "alpha" in second_list  # user_plugin_dir unchanged, still discovered


# --- History -----------------------------------------------------------------


def test_history_is_empty_at_the_start(repo: Path) -> None:
    session = InteractiveSession(repo, use_persistence=False)

    assert session.dispatch("history") == "(empty)"


def test_history_lists_commands_via_run_interactive(repo: Path) -> None:
    output_lines: list[str] = []
    read_line = _scripted(["ask runtime", "search evidence", "history", "exit"])

    run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    history_output = next(line for line in output_lines if line.startswith("  1."))
    assert "1. ask runtime" in history_output
    assert "2. search evidence" in history_output
    assert "3. history" in history_output


# --- run_interactive() end-to-end (scripted) ------------------------------------


def test_run_interactive_full_scripted_session(repo: Path) -> None:
    output_lines: list[str] = []
    read_line = _scripted(["help", "ask runtime", "exit"])

    exit_code = run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert any("Question: runtime" in line for line in output_lines)
    assert output_lines[-1] == "Goodbye."


def test_run_interactive_prints_welcome_message(repo: Path) -> None:
    output_lines: list[str] = []
    read_line = _scripted(["exit"])

    run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert "interactive session" in output_lines[0]


def test_run_interactive_quit_is_equivalent_to_exit(repo: Path) -> None:
    output_lines: list[str] = []
    read_line = _scripted(["quit"])

    exit_code = run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert output_lines[-1] == "Goodbye."


def test_run_interactive_eof_exits_gracefully_without_an_exit_command(repo: Path) -> None:
    output_lines: list[str] = []
    read_line = _scripted([])  # immediately raises EOFError

    exit_code = run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert output_lines[-1] == "Goodbye."


def test_run_interactive_keyboard_interrupt_reprompts_instead_of_exiting(repo: Path) -> None:
    calls = {"count": 0}
    remaining = iter(["ask runtime", "exit"])

    def read_line(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise KeyboardInterrupt
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError

    output_lines: list[str] = []
    exit_code = run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert any("Question: runtime" in line for line in output_lines)


def test_run_interactive_unexpected_exception_does_not_kill_the_session(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ocom_reader.interactive as interactive_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(interactive_module, "run_ask", boom)
    output_lines: list[str] = []
    read_line = _scripted(["ask runtime", "search runtime", "exit"])

    exit_code = run_interactive(repo, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert any("Error: boom" in line for line in output_lines)
    assert any("docs/architecture/ADR-001-runtime.md" in line for line in output_lines)  # session kept working


def test_run_interactive_prompt_reflects_the_active_repository(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "another_repo"
    _write(other, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    prompts: list[str] = []

    commands = iter(["ask runtime", f"use {other}", "ask adr", "exit"])

    def read_line(prompt: str) -> str:
        prompts.append(prompt)
        try:
            return next(commands)
        except StopIteration:
            raise EOFError

    run_interactive(repo, use_persistence=False, read_line=read_line, write=lambda s: None)

    assert repo.name in prompts[0]
    assert other.name in prompts[-1]


# --- Persistence flag propagation -----------------------------------------


def test_use_persistence_false_never_writes_ocom(repo: Path) -> None:
    read_line = _scripted(["ask runtime", "exit"])

    run_interactive(repo, use_persistence=False, read_line=read_line, write=lambda s: None)

    assert not (repo / ".ocom").exists()


def test_use_persistence_true_writes_ocom(repo: Path) -> None:
    read_line = _scripted(["ask runtime", "exit"])

    run_interactive(repo, use_persistence=True, read_line=read_line, write=lambda s: None)

    assert (repo / ".ocom").exists()


# --- Real repository integration --------------------------------------------


def test_scripted_session_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_lines: list[str] = []
    read_line = _scripted(["ask runtime", "search registry", "history", "exit"])

    exit_code = run_interactive(repo_root, use_persistence=False, read_line=read_line, write=output_lines.append)

    assert exit_code == 0
    assert any("Question: runtime" in line for line in output_lines)


def test_cli_entry_point_via_real_piped_stdin_subprocess(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable, "-m", "ocom_reader",
            "--repo", str(repo_root), "--no-cache",
            "--workspace-file", str(tmp_path / "workspace.json"),
        ],
        input="ask runtime\nexit\n",
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0
    assert "Question: runtime" in result.stdout
    assert "Goodbye." in result.stdout


def test_cli_entry_point_via_real_piped_stdin_without_explicit_exit(tmp_path: Path) -> None:
    """Piped stdin hits EOF at the end of input even with no `exit`
    command — must still exit cleanly, matching a real Ctrl-D."""
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable, "-m", "ocom_reader",
            "--repo", str(repo_root), "--no-cache",
            "--workspace-file", str(tmp_path / "workspace.json"),
        ],
        input="ask registry\n",
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0
    assert "Goodbye." in result.stdout
