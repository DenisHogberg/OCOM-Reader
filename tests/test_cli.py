"""CLI (M009-010) — argument parsing and subcommand behavior.

Runs cli.main() in-process (capturing stdout) against a small synthetic
repository rather than shelling out, so tests stay fast and don't
depend on the package being pip-installed. One real-repository smoke
test at the bottom exercises the actual installed console entry point.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ocom_reader.cli import main


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


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


def test_missing_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_unknown_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["bogus-command", "query"])


# --- Real repository smoke test (installed console script) --------------------


def test_console_script_ask_against_the_real_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "ocom_reader", "--repo", str(repo_root), "ask", "identity resolution"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0
    assert "Question: identity resolution" in result.stdout
    assert "Answer" in result.stdout
