"""Multi-Repository Workspace (M016).

Most scenarios use small, synthetic repositories (tmp_path) and a
tmp_path-scoped workspace state file — never the real home directory.
The real-repository section (bottom) uses only this project's own
repository (portable, per every prior milestone's discipline).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ocom_reader.reader import Reader
from ocom_reader.workspace import WorkspaceError, WorkspaceManager


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _manager(tmp_path: Path) -> WorkspaceManager:
    return WorkspaceManager(state_path=tmp_path / "workspace.json")


@pytest.fixture()
def repo_a(tmp_path: Path) -> Path:
    root = tmp_path / "repo_a"
    _write(root, "docs/architecture/ADR-001-alpha.md", "# Alpha\n\nBody.")
    return root


@pytest.fixture()
def repo_b(tmp_path: Path) -> Path:
    root = tmp_path / "repo_b"
    _write(root, "docs/architecture/ADR-001-beta.md", "# Beta\n\nBody.")
    return root


# --- add() ------------------------------------------------------------------


def test_add_registers_a_repository(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)

    entry = wm.add("alpha", repo_a)

    assert entry.name == "alpha"
    assert entry.path == str(repo_a.resolve())


def test_add_a_nonexistent_path_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.add("nope", tmp_path / "does-not-exist")


def test_add_a_duplicate_name_raises(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    with pytest.raises(WorkspaceError):
        wm.add("alpha", repo_b)


def test_first_added_repository_becomes_active_automatically(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)

    wm.add("alpha", repo_a)

    assert wm.active() is not None
    assert wm.active().name == "alpha"


def test_second_added_repository_does_not_change_the_active_one(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    wm.add("beta", repo_b)

    assert wm.active().name == "alpha"


# --- list() -----------------------------------------------------------------


def test_list_is_empty_initially(tmp_path: Path) -> None:
    assert _manager(tmp_path).list() == []


def test_list_returns_all_registered_repositories(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    names = {e.name for e in wm.list()}

    assert names == {"alpha", "beta"}


# --- use() ------------------------------------------------------------------


def test_use_switches_the_active_repository(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    entry = wm.use("beta")

    assert entry.name == "beta"
    assert wm.active().name == "beta"


def test_use_an_unknown_name_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.use("nope")


# --- remove() -----------------------------------------------------------


def test_remove_unregisters_a_repository(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    wm.remove("alpha")

    assert wm.list() == []


def test_remove_the_active_repository_clears_active_without_guessing_a_replacement(
    tmp_path: Path, repo_a: Path, repo_b: Path
) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    wm.remove("alpha")

    assert wm.active() is None
    assert [e.name for e in wm.list()] == ["beta"]


def test_remove_an_inactive_repository_leaves_active_unchanged(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    wm.remove("beta")

    assert wm.active().name == "alpha"


def test_remove_never_deletes_the_repository_files(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    wm.remove("alpha")

    assert repo_a.exists()
    assert (repo_a / "docs" / "architecture" / "ADR-001-alpha.md").exists()


def test_remove_an_unknown_name_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.remove("nope")


# --- resolve() ----------------------------------------------------------


def test_resolve_by_name(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    assert wm.resolve("alpha") == repo_a.resolve()


def test_resolve_with_no_name_uses_active(tmp_path: Path, repo_a: Path, repo_b: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)
    wm.use("beta")

    assert wm.resolve() == repo_b.resolve()


def test_resolve_with_no_active_and_no_name_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.resolve()


def test_resolve_unknown_name_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.resolve("nope")


# --- storage_path() / is_initialized() -------------------------------------


def test_storage_path_is_the_dot_ocom_inside_the_repository(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    assert wm.storage_path("alpha") == repo_a.resolve() / ".ocom"


def test_is_initialized_false_before_any_reader_use(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    assert wm.is_initialized("alpha") is False


def test_is_initialized_true_after_reader_use(tmp_path: Path, repo_a: Path) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)

    Reader(wm.resolve("alpha"), use_persistence=True)

    assert wm.is_initialized("alpha") is True


def test_storage_path_of_unknown_name_raises(tmp_path: Path) -> None:
    wm = _manager(tmp_path)

    with pytest.raises(WorkspaceError):
        wm.storage_path("nope")


# --- Persistence across instances -----------------------------------------


def test_state_persists_across_manager_instances(tmp_path: Path, repo_a: Path) -> None:
    state_path = tmp_path / "workspace.json"
    WorkspaceManager(state_path=state_path).add("alpha", repo_a)

    reloaded = WorkspaceManager(state_path=state_path)

    assert [e.name for e in reloaded.list()] == ["alpha"]
    assert reloaded.active().name == "alpha"


def test_a_fresh_state_path_with_nothing_in_it_is_empty(tmp_path: Path) -> None:
    wm = WorkspaceManager(state_path=tmp_path / "does-not-exist-yet.json")

    assert wm.list() == []
    assert wm.active() is None


# --- Isolation: two repositories never interfere with one another --------


def test_two_workspace_repositories_get_independent_ocom_directories(
    tmp_path: Path, repo_a: Path, repo_b: Path
) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    Reader(wm.resolve("alpha"), use_persistence=True)
    Reader(wm.resolve("beta"), use_persistence=True)

    assert (repo_a / ".ocom").exists()
    assert (repo_b / ".ocom").exists()
    assert (repo_a / ".ocom" / "index.json").read_text() != (repo_b / ".ocom" / "index.json").read_text()


def test_switching_active_repository_produces_independent_answers(
    tmp_path: Path, repo_a: Path, repo_b: Path
) -> None:
    wm = _manager(tmp_path)
    wm.add("alpha", repo_a)
    wm.add("beta", repo_b)

    wm.use("alpha")
    answer_alpha = Reader(wm.resolve(), use_persistence=False).answer("alpha")

    wm.use("beta")
    answer_beta = Reader(wm.resolve(), use_persistence=False).answer("beta")

    assert answer_alpha.grounded is True
    assert answer_beta.grounded is True
    assert answer_alpha.evidence[0].document.registry_id != answer_beta.evidence[0].document.registry_id


# --- Real repository integration --------------------------------------------


def test_workspace_against_the_real_ocom_reader_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    wm = _manager(tmp_path)

    entry = wm.add("ocom-reader", repo_root)

    assert entry.path == str(repo_root.resolve())
    assert wm.active().name == "ocom-reader"
    assert wm.resolve() == repo_root.resolve()

    reader = Reader(wm.resolve(), use_persistence=False)
    answer = reader.answer("runtime")
    assert answer.grounded is True
