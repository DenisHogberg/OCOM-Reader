"""Web UI server (M018) — real `ThreadingHTTPServer` on an ephemeral
port, real HTTP requests via `urllib`. Not mocked: this is the same
discipline every prior milestone's real-repository verification used,
applied to the network layer this milestone introduces.
"""

from __future__ import annotations

import concurrent.futures
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

import pytest

from ocom_reader.web.server import start_server
from ocom_reader.workspace import WorkspaceManager


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(root, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\n**Builds on:** [Runtime](ADR-001-runtime.md)\n\nBody.")
    return root


@pytest.fixture()
def running_server(repo: Path, tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    server = start_server(
        host="127.0.0.1",
        port=port,
        repository_root=repo,
        workspace_state_path=tmp_path / "workspace.json",
        use_persistence=False,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(base_url: str, path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# --- Basic routing ------------------------------------------------------


def test_health(running_server: str) -> None:
    status, data = _get(running_server, "/api/health")

    assert status == 200
    assert data["status"] == "ok"


def test_static_index(running_server: str) -> None:
    with urllib.request.urlopen(f"{running_server}/") as resp:
        body = resp.read().decode()
    assert resp.status == 200
    assert "OCOM Reader" in body
    assert resp.headers["Content-Type"].startswith("text/html")


def test_static_app_js(running_server: str) -> None:
    with urllib.request.urlopen(f"{running_server}/app.js") as resp:
        body = resp.read().decode()
    assert "fetch" in body


def test_unknown_static_path_is_404(running_server: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{running_server}/does-not-exist.html")
    assert exc_info.value.code == 404


def test_path_traversal_is_blocked(running_server: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{running_server}/../server.py")
    assert exc_info.value.code == 404


def test_unknown_api_path_is_404(running_server: str) -> None:
    status, data = _get(running_server, "/api/does-not-exist")
    assert status == 404


# --- API endpoints ----------------------------------------------------------


def test_ask_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/ask?q=runtime")

    assert status == 200
    assert data["grounded"] is True
    assert data["evidence"][0]["document"]["registry_id"] == "docs/architecture/ADR-001-runtime.md"


def test_ask_endpoint_missing_query_is_400(running_server: str) -> None:
    status, data = _get(running_server, "/api/ask")

    assert status == 400
    assert "error" in data


def test_search_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/search?q=runtime")

    assert status == 200
    assert len(data["matches"]) >= 1


def test_related_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/related?id=docs/architecture/ADR-002-evidence.md")

    assert status == 200
    assert any(e["registry_id"] == "docs/architecture/ADR-001-runtime.md" for e in data["related"])


def test_explain_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/explain?q=runtime")

    assert status == 200
    assert len(data["documents"]) >= 1


def test_workspace_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/workspace")

    assert status == 200
    assert data == {"repositories": [], "active": None}


def test_plugins_endpoint(running_server: str) -> None:
    status, data = _get(running_server, "/api/plugins")

    assert status == 200
    assert data == {"plugins": []}


def test_unknown_repo_query_param_is_404(running_server: str) -> None:
    status, data = _get(running_server, "/api/ask?q=runtime&repo=nonexistent")

    assert status == 404


# --- Multiple repositories ------------------------------------------------


def test_multiple_repositories_via_repo_param(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other_repo"
    _write(other, "docs/architecture/ADR-001-alpha.md", "# Alpha Concept\n\nBody.")
    ws_path = tmp_path / "workspace.json"
    wm = WorkspaceManager(state_path=ws_path)
    wm.add("primary", repo)  # added first -> becomes active, matching the server's own --repo default
    wm.add("other", other)

    port = _free_port()
    server = start_server(
        host="127.0.0.1", port=port, repository_root=repo, workspace_state_path=ws_path, use_persistence=False
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        _, default_result = _get(base, "/api/ask?q=runtime")
        _, other_result = _get(base, "/api/ask?q=alpha&repo=other")

        assert default_result["evidence"][0]["document"]["registry_id"] == "docs/architecture/ADR-001-runtime.md"
        assert other_result["evidence"][0]["document"]["registry_id"] == "docs/architecture/ADR-001-alpha.md"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_selecting_a_repository_never_mutates_the_workspace_active_pointer(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other_repo"
    _write(other, "docs/architecture/ADR-001-alpha.md", "# Alpha\n\nBody.")
    ws_path = tmp_path / "workspace.json"
    wm = WorkspaceManager(state_path=ws_path)
    wm.add("first", repo)
    wm.add("second", other)

    port = _free_port()
    server = start_server(host="127.0.0.1", port=port, repository_root=repo, workspace_state_path=ws_path, use_persistence=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        _get(base, "/api/ask?q=alpha&repo=second")  # never calls a "use" endpoint - none exists
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    reloaded = WorkspaceManager(state_path=ws_path)
    assert reloaded.active().name == "first"  # unchanged - "first" was registered first


# --- Determinism / CLI parity -------------------------------------------


def test_identical_answers_between_direct_reader_and_web_api(running_server: str, repo: Path) -> None:
    from ocom_reader.reader import Reader

    direct = Reader(repo, use_persistence=False).answer("runtime").model_dump(mode="json")
    _, via_http = _get(running_server, "/api/ask?q=runtime")

    assert direct == via_http


def test_repeated_requests_are_deterministic(running_server: str) -> None:
    _, first = _get(running_server, "/api/ask?q=runtime")
    _, second = _get(running_server, "/api/ask?q=runtime")

    assert first == second


# --- Concurrency (real threads, real sockets) --------------------------------


def test_concurrent_requests_all_succeed(running_server: str) -> None:
    def fetch(i: int) -> int:
        status, _ = _get(running_server, f"/api/ask?q=runtime")
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch, range(30)))

    assert all(status == 200 for status in results)


def test_concurrent_writes_to_the_same_repository_produce_a_consistent_snapshot(
    repo: Path, tmp_path: Path
) -> None:
    port = _free_port()
    server = start_server(
        host="127.0.0.1", port=port, repository_root=repo, workspace_state_path=tmp_path / "workspace.json",
        use_persistence=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"

        def fetch(i: int) -> int:
            status, _ = _get(base, "/api/ask?q=runtime")
            return status

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch, range(20)))

        assert all(status == 200 for status in results)

        from ocom_reader.persistence import PersistentStore

        store = PersistentStore(repo)
        index = store.load_index()
        registry = store.load_registry()
        assert len(index.entries) == len(registry.entries) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --- Real repository integration --------------------------------------------


def test_server_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    port = _free_port()
    server = start_server(host="127.0.0.1", port=port, repository_root=repo_root, use_persistence=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        status, data = _get(base, "/api/ask?q=identity+resolution")
        assert status == 200
        assert data["grounded"] is True

        status, health = _get(base, "/api/health")
        assert status == 200
        assert health["reader_version"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
