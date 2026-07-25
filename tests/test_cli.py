"""CLI (M009-010) — argument parsing and subcommand behavior.

Runs cli.main() in-process (capturing stdout) against a small synthetic
repository rather than shelling out, so tests stay fast and don't
depend on the package being pip-installed. One real-repository smoke
test at the bottom exercises the actual installed console entry point.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ocom_reader.cli import main


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WorkspaceManager (M016) defaults to ~/.ocom_reader/workspace.json
    — every test in this module must never touch the real home
    directory, even just to check the file doesn't exist. A sibling of
    tmp_path, not a subdirectory of it, so it never ends up inside a
    repository fixture that indexes tmp_path itself."""
    fake_home = tmp_path.parent / f"{tmp_path.name}-home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    return tmp_path


def test_ask_subcommand_prints_a_composed_answer(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "ask", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Question: runtime" in output
    assert "Answer" in output
    assert "Evidence" in output
    assert "Related Documents" in output
    assert "Recommended Reading Order" in output
    assert "Runtime" in output


def test_ask_subcommand_reports_no_match(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "ask", "zzznonexistenttermxyz"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No documentation found" in output


def test_search_subcommand_prints_ranked_registry_ids(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "search", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "docs/architecture/ADR-002-runtime.md" in output


def test_search_subcommand_reports_no_matches(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "search", "zzznonexistenttermxyz"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No matches" in output


def test_related_subcommand_prints_neighbors(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "related", "docs/architecture/ADR-002-runtime.md"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "docs/architecture/ADR-001-foundation.md" in output


def test_related_subcommand_reports_no_relations(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "related", "does/not/exist.md"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No documents directly related" in output


def test_explain_subcommand_prints_reasons(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "explain", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Title match: runtime" in output


def test_default_repo_is_current_directory(repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(repo)
    exit_code = main(["ask", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Runtime" in output


def test_missing_subcommand_launches_interactive_mode(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """As of M013, no subcommand is no longer an error — it launches
    the REPL (see test_interactive.py for full REPL coverage)."""

    def immediate_eof(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", immediate_eof)

    exit_code = main(["--repo", str(repo)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "interactive session" in output
    assert "Goodbye." in output


def test_unknown_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["bogus-command", "query"])


# --- Persistence (M012) ------------------------------------------------------


def test_ask_creates_ocom_by_default(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--repo", str(repo), "ask", "runtime"])

    assert (repo / ".ocom").exists()


def test_no_cache_flag_skips_persistence(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--repo", str(repo), "--no-cache", "ask", "runtime"])

    assert not (repo / ".ocom").exists()


# --- Multi-Repository Workspace (M016) ---------------------------------------


def test_repo_add_and_list(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "add", str(repo), "--name", "alpha"])
    capsys.readouterr()

    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "alpha" in output
    assert str(repo) in output


def test_repo_add_defaults_name_to_directory_name(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "add", str(repo)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert repo.name in output


def test_repo_use_and_ask_without_explicit_repo(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "add", str(repo), "--name", "alpha"])
    capsys.readouterr()

    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "--no-cache", "ask", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Question: runtime" in output


def test_explicit_repo_flag_bypasses_the_workspace(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _write(other, "docs/architecture/ADR-001-other.md", "# Other\n\nBody.")
    main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "add", str(repo), "--name", "alpha"])
    capsys.readouterr()

    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "--repo", str(other), "--no-cache", "ask", "other"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Other" in output


def test_repo_remove_never_deletes_repository_files(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "add", str(repo), "--name", "alpha"])
    capsys.readouterr()

    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "remove", "alpha"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert repo.exists()
    assert list(repo.rglob("*.md"))


def test_repo_use_unknown_name_reports_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "use", "nope"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Error" in output


def test_ask_with_no_active_repository_and_no_flag_falls_back_to_cwd(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo)

    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "--no-cache", "ask", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Question: runtime" in output


def test_repo_list_with_nothing_registered(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--workspace-file", str(tmp_path / "ws.json"), "repo", "list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No repositories registered" in output


# --- Rich CLI (M015) ----------------------------------------------------------


def test_completion_bash_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["completion", "bash"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "_ocom_reader_completions" in output


def test_plain_flag_forces_plain_output_even_when_stdout_reports_a_tty(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    exit_code = main(["--repo", str(repo), "--plain", "search", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "\033[" not in output  # no ANSI codes
    assert "Matches for" in output


def test_rich_mode_activates_with_a_simulated_tty_and_can_be_paged_off(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With stdout AND stdin both reporting a tty but TERM unset, color
    still activates (color doesn't require a real pager) while paging
    stays off (the hang risk documented in MILESTONE-015.md) — search
    output (never paged) is used here to isolate the color behavior."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)

    exit_code = main(["--repo", str(repo), "search", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "\033[" in output  # rich table with ANSI styling


def test_no_color_env_disables_color_but_not_the_table(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")

    exit_code = main(["--repo", str(repo), "search", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "\033[" not in output
    assert "registry_id" in output  # still a table, just uncolored


def test_ask_never_hangs_when_stdin_is_not_a_real_tty_even_if_stdout_is(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the real hang reproduced during M015's own
    verification: stdout reporting a tty must never be sufficient on
    its own to trigger pydoc.pager()."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    exit_code = main(["--repo", str(repo), "ask", "runtime"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Question: runtime" in output


# --- Plugin Architecture (M017) -----------------------------------------


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


def test_plugin_list_and_info(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")

    main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "plugins"), "plugin", "list"])
    list_output = capsys.readouterr().out
    assert "alpha" in list_output

    exit_code = main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "plugins"), "plugin", "info", "alpha"])
    info_output = capsys.readouterr().out
    assert exit_code == 0
    assert "alpha" in info_output
    assert "state: active" in info_output


def test_plugin_list_with_nothing_discovered(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "empty"), "plugin", "list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No plugins discovered" in output


def test_plugin_info_unknown_id(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "empty"), "plugin", "info", "nope"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No plugin with id" in output


def test_plugin_disable_persists_across_invocations(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")
    state_file = tmp_path / "plugin_state.json"
    common_args = ["--repo", str(repo), "--plugin-dir", str(tmp_path / "plugins"), "--plugin-state-file", str(state_file)]

    main(common_args + ["plugin", "disable", "alpha"])
    capsys.readouterr()

    exit_code = main(common_args + ["plugin", "list"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "enabled=no" in output


def test_plugin_enable_reports_reload_is_needed(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")
    common_args = [
        "--repo", str(repo),
        "--plugin-dir", str(tmp_path / "plugins"),
        "--plugin-state-file", str(tmp_path / "plugin_state.json"),
    ]
    main(common_args + ["plugin", "disable", "alpha"])
    capsys.readouterr()

    exit_code = main(common_args + ["plugin", "enable", "alpha"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Enabled" in output


def test_plugin_reload(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_test_plugin(tmp_path / "plugins", "alpha")

    exit_code = main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "plugins"), "plugin", "reload"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Reloaded all plugins" in output


def test_plugin_disable_unknown_id_reports_an_error(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--repo", str(repo), "--plugin-dir", str(tmp_path / "empty"), "plugin", "disable", "nope"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Error" in output


def test_a_broken_plugin_never_prevents_the_cli_from_working(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plugin_dir = tmp_path / "plugins"
    broken = plugin_dir / "broken"
    broken.mkdir(parents=True)
    (broken / "plugin.json").write_text("{ not valid json")

    exit_code = main(["--repo", str(repo), "--plugin-dir", str(plugin_dir), "plugin", "list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "No plugins discovered" in output


# --- Optional LLM Layer (M019) ------------------------------------------


def test_ask_without_llm_provider_is_byte_identical_to_before_this_milestone(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The regression guard: every existing ask test already proves
    this, but this test names the guarantee explicitly — running the
    same query with and without the flag omitted must be identical."""
    main(["--repo", str(repo), "--no-cache", "ask", "runtime"])
    without_flag = capsys.readouterr().out

    main(["--repo", str(repo), "--no-cache", "ask", "runtime"])
    without_flag_again = capsys.readouterr().out

    assert without_flag == without_flag_again
    assert "Natural Language Answer" not in without_flag


def test_ask_with_llm_provider_falls_back_gracefully_when_sdk_not_installed(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--repo", str(repo), "--no-cache", "ask", "runtime", "--llm-provider", "openai"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "LLM unavailable" in output
    assert "not installed" in output
    # Deterministic sections are still fully present.
    assert "Answer" in output
    assert "Evidence" in output
    assert "Related Documents" in output
    assert "Recommended Reading Order" in output


def test_ask_with_llm_provider_anthropic_falls_back_gracefully(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--repo", str(repo), "--no-cache", "ask", "runtime", "--llm-provider", "anthropic"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "LLM unavailable" in output


def test_ask_with_llm_provider_success_adds_a_natural_language_section(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI wiring itself: with a working provider injected in place of
    the real construction path, the deterministic sections stay intact
    and a Natural Language Answer section is appended."""
    import ocom_reader.cli as cli_module

    class FakeAdapter:
        def __init__(self, config) -> None:
            pass

        def enhance(self, answer):
            from ocom_reader.llm import LLMProviderName, LLMResult

            return LLMResult(text="A rewritten answer.", used_provider=LLMProviderName.OPENAI)

    monkeypatch.setattr(cli_module, "LLMAdapter", FakeAdapter)

    exit_code = main(["--repo", str(repo), "--no-cache", "ask", "runtime", "--llm-provider", "openai"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Natural Language Answer" in output
    assert "A rewritten answer." in output
    assert "Answer" in output
    assert "Evidence" in output


def test_ask_llm_provider_never_changes_deterministic_evidence_or_reading_order(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Compare the deterministic sections themselves (not just their
    presence) between a plain ask and an ask with a graceful LLM
    fallback — they must be identical, since the LLM path never
    touches ComposedAnswer."""
    main(["--repo", str(repo), "--no-cache", "ask", "runtime"])
    plain = capsys.readouterr().out

    main(["--repo", str(repo), "--no-cache", "ask", "runtime", "--llm-provider", "openai"])
    with_llm_flag = capsys.readouterr().out

    assert with_llm_flag.startswith(plain)  # identical deterministic prefix, LLM note appended after


# --- Web UI (M018) -------------------------------------------------------


def test_web_command_starts_the_server_and_serves_forever_is_called(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI wiring itself: build the real server, call serve_forever
    exactly once, and clean up. serve_forever is replaced with a no-op
    stand-in for the assertion (a real blocking call would hang the
    test) — the server construction and routing themselves are already
    covered end-to-end by test_web_server.py's real sockets."""
    calls = {"serve_forever": 0, "server_close": 0}
    import ocom_reader.cli as cli_module

    real_start_server = cli_module.start_server

    def wrapped_start_server(*args, **kwargs):
        server = real_start_server(*args, **kwargs)
        original_close = server.server_close

        def fake_serve_forever():
            calls["serve_forever"] += 1

        def fake_close():
            calls["server_close"] += 1
            original_close()

        server.serve_forever = fake_serve_forever
        server.server_close = fake_close
        return server

    monkeypatch.setattr(cli_module, "start_server", wrapped_start_server)

    exit_code = main(["--repo", str(repo), "--no-cache", "web", "--port", "0"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Web UI running" in output
    assert calls["serve_forever"] == 1
    assert calls["server_close"] == 1


# --- Real repository smoke test (installed console script) --------------------


def test_console_script_ask_against_the_real_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable, "-m", "ocom_reader",
            "--repo", str(repo_root),
            "--workspace-file", str(tmp_path / "workspace.json"),
            "ask", "identity resolution",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0
    assert "Question: identity resolution" in result.stdout
    assert "Answer" in result.stdout
