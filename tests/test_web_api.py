"""Web UI internal API (M018) — handler functions called directly, no
real socket. `test_web_server.py` covers the actual HTTP layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ocom_reader.web import api as web_api
from ocom_reader.workspace import WorkspaceManager


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(root, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\n**Builds on:** [Runtime](ADR-001-runtime.md)\n\nBody.")
    return root


def _workspace(tmp_path: Path) -> WorkspaceManager:
    return WorkspaceManager(state_path=tmp_path / "workspace.json")


# --- resolve_repo_path ---------------------------------------------------


def test_resolve_repo_path_by_name(repo: Path, tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    ws.add("alpha", repo)

    resolved = web_api.resolve_repo_path("alpha", Path("."), ws)

    assert resolved == repo.resolve()


def test_resolve_repo_path_unknown_name_raises(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)

    with pytest.raises(web_api.ApiError) as exc_info:
        web_api.resolve_repo_path("nope", Path("."), ws)
    assert exc_info.value.status == 404


def test_resolve_repo_path_falls_back_to_active(repo: Path, tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    ws.add("alpha", repo)

    resolved = web_api.resolve_repo_path(None, Path("."), ws)

    assert resolved == repo.resolve()


def test_resolve_repo_path_falls_back_to_default_repo_when_nothing_active(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)

    resolved = web_api.resolve_repo_path(None, Path("/some/default"), ws)

    assert resolved == Path("/some/default")


# --- get_health ---------------------------------------------------------


def test_get_health() -> None:
    result = web_api.get_health()

    assert result["status"] == "ok"
    assert result["reader_version"]


# --- get_workspace --------------------------------------------------------


def test_get_workspace_empty(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)

    result = web_api.get_workspace(ws)

    assert result == {"repositories": [], "active": None}


def test_get_workspace_lists_repositories_and_marks_active(repo: Path, tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    ws.add("alpha", repo)

    result = web_api.get_workspace(ws)

    assert result["active"] == "alpha"
    assert result["repositories"][0]["name"] == "alpha"
    assert result["repositories"][0]["active"] is True


# --- get_plugins ----------------------------------------------------------


def test_get_plugins_with_nothing_discovered(repo: Path, tmp_path: Path) -> None:
    result = web_api.get_plugins(repo, {"user_plugin_dir": tmp_path / "no-plugins"})

    assert result == {"plugins": []}


# --- get_ask / get_search / get_related / get_explain -----------------------


def test_get_ask(repo: Path) -> None:
    result = web_api.get_ask(repo, "runtime", use_persistence=False)

    assert result["query"] == "runtime"
    assert result["grounded"] is True
    assert result["evidence"][0]["document"]["registry_id"] == "docs/architecture/ADR-001-runtime.md"


def test_get_ask_missing_query_raises(repo: Path) -> None:
    with pytest.raises(web_api.ApiError):
        web_api.get_ask(repo, "", use_persistence=False)


def test_get_ask_matches_direct_reader_call(repo: Path) -> None:
    from ocom_reader.reader import Reader

    direct = Reader(repo, use_persistence=False).answer("runtime").model_dump(mode="json")
    via_api = web_api.get_ask(repo, "runtime", use_persistence=False)

    assert direct == via_api


def test_get_search(repo: Path) -> None:
    result = web_api.get_search(repo, "runtime", use_persistence=False)

    assert result["query"] == "runtime"
    assert len(result["matches"]) >= 1


def test_get_search_missing_query_raises(repo: Path) -> None:
    with pytest.raises(web_api.ApiError):
        web_api.get_search(repo, "", use_persistence=False)


def test_get_related(repo: Path) -> None:
    result = web_api.get_related(repo, "docs/architecture/ADR-002-evidence.md", use_persistence=False)

    assert result["registry_id"] == "docs/architecture/ADR-002-evidence.md"
    assert any(e["registry_id"] == "docs/architecture/ADR-001-runtime.md" for e in result["related"])


def test_get_related_unknown_id_is_empty(repo: Path) -> None:
    result = web_api.get_related(repo, "does/not/exist.md", use_persistence=False)

    assert result["related"] == []


def test_get_related_missing_id_raises(repo: Path) -> None:
    with pytest.raises(web_api.ApiError):
        web_api.get_related(repo, "", use_persistence=False)


def test_get_explain(repo: Path) -> None:
    result = web_api.get_explain(repo, "runtime", use_persistence=False)

    assert result["query"] == "runtime"
    assert len(result["documents"]) >= 1
    assert result["documents"][0]["reasons"]


def test_get_explain_missing_query_raises(repo: Path) -> None:
    with pytest.raises(web_api.ApiError):
        web_api.get_explain(repo, "", use_persistence=False)


# --- Concurrency safety (unit-level) -----------------------------------------


def test_construction_lock_serializes_concurrent_saves(repo: Path) -> None:
    import threading

    results = []
    errors = []

    def worker() -> None:
        try:
            results.append(web_api.get_ask(repo, "runtime", use_persistence=True))
        except Exception as exc:  # pragma: no cover - only on real failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 10
    assert all(r == results[0] for r in results)
