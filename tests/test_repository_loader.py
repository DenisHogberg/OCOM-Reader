"""Repository Loader v0.2 (M012 revision).

M011's `RepositoryLoader` used its own standalone `JSONIndexStore`
(external cache dir, keyed by a path hash) and saved on every `load()`.
M012 retired that store: `RepositoryLoader` now reads/diffs only,
backed by `persistence.PersistentStore` (`.ocom/` inside the indexed
repository) — see MILESTONE-012.md for why writing moved to `Reader`.
These tests exercise `RepositoryLoader`'s own contract directly against
a `PersistentStore`-backed `.ocom/`; `tests/test_persistence.py` covers
`PersistentStore` itself, and `tests/test_reader_pipeline.py` covers
the write side through `Reader`.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.indexer import RepositoryIndexBuilder
from ocom_reader.loader import ChangeSet, RepositoryLoader
from ocom_reader.persistence import PersistentStore
from ocom_reader.registry import RegistryBuilder


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _persist(repository_root: Path) -> None:
    """Simulate what Reader does: build + save a full snapshot."""
    index = RepositoryIndexBuilder(repository_root).build()
    registry = RegistryBuilder().build(index)
    PersistentStore(repository_root).save(index, registry)


# --- load() / reopen() --------------------------------------------------------


def test_reopen_with_nothing_stored_is_none(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    loader = RepositoryLoader()

    assert loader.reopen(tmp_path) is None


def test_load_with_nothing_stored_returns_a_fresh_index_without_writing(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    loader = RepositoryLoader()

    index = loader.load(tmp_path)

    assert len(index.entries) == 1
    assert not (tmp_path / ".ocom").exists()


def test_load_reuses_the_stored_index_when_nothing_changed(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    _persist(tmp_path)
    loader = RepositoryLoader()

    stored = loader.reopen(tmp_path)
    loaded = loader.load(tmp_path)

    assert loaded.model_dump() == stored.model_dump()


def test_load_returns_a_fresh_index_reflecting_real_changes(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nOriginal body.")
    _persist(tmp_path)
    loader = RepositoryLoader()
    stored = loader.reopen(tmp_path)

    _write(tmp_path, "docs/a.md", "# A\n\nCompletely different body text now.")
    loaded = loader.load(tmp_path)

    assert loaded.entries[0].content_hash != stored.entries[0].content_hash


def test_load_does_not_write_even_when_it_detects_changes(tmp_path: Path) -> None:
    """RepositoryLoader never writes — only Reader does, once it also
    has a KnowledgeRegistry to save alongside the index (MILESTONE-012.md)."""
    _write(tmp_path, "docs/a.md", "# A\n\nOriginal body.")
    _persist(tmp_path)
    before = (tmp_path / ".ocom" / "index.json").read_text()
    loader = RepositoryLoader()

    _write(tmp_path, "docs/a.md", "# A\n\nCompletely different body text now.")
    loader.load(tmp_path)

    after = (tmp_path / ".ocom" / "index.json").read_text()
    assert before == after


# --- detect_changes() ----------------------------------------------------------


def test_detect_changes_reports_added_modified_removed(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    _write(tmp_path, "docs/b.md", "# B\n\nBody.")
    previous = RepositoryIndexBuilder(tmp_path).build()

    (tmp_path / "docs" / "b.md").unlink()
    _write(tmp_path, "docs/a.md", "# A\n\nCompletely different body text now.")
    _write(tmp_path, "docs/c.md", "# C\n\nBrand new document.")
    current = RepositoryIndexBuilder(tmp_path).build()

    changes = RepositoryLoader().detect_changes(previous, current)

    assert changes.added == ["docs/c.md"]
    assert changes.modified == ["docs/a.md"]
    assert changes.removed == ["docs/b.md"]
    assert changes.has_changes is True


def test_detect_changes_is_empty_when_nothing_changed(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    previous = RepositoryIndexBuilder(tmp_path).build()
    current = RepositoryIndexBuilder(tmp_path).build()

    changes = RepositoryLoader().detect_changes(previous, current)

    assert changes == ChangeSet(added=[], modified=[], removed=[])
    assert changes.has_changes is False


def test_detect_changes_on_two_fresh_empty_indexes_has_no_changes(tmp_path: Path) -> None:
    empty1 = RepositoryIndexBuilder(tmp_path).build()
    empty2 = RepositoryIndexBuilder(tmp_path).build()

    assert RepositoryLoader().detect_changes(empty1, empty2).has_changes is False


# --- Format compatibility (delegates to PersistentStore) -----------------------


def test_compatibility_is_false_when_nothing_is_stored_yet(tmp_path: Path) -> None:
    compat = RepositoryLoader().check_compatibility(tmp_path)

    assert compat.compatible is False
    assert compat.stored_version is None


def test_compatibility_is_true_after_a_normal_save(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    _persist(tmp_path)

    compat = RepositoryLoader().check_compatibility(tmp_path)

    assert compat.compatible is True
    assert compat.stored_version == compat.current_version


# --- Edge cases -----------------------------------------------------------


def test_loading_an_empty_repository_produces_an_empty_index(tmp_path: Path) -> None:
    index = RepositoryLoader().load(tmp_path)

    assert index.entries == []


def test_load_is_deterministic_across_repeated_calls(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    _persist(tmp_path)
    loader = RepositoryLoader()

    first = loader.load(tmp_path).model_dump()
    second = loader.load(tmp_path).model_dump()

    assert first == second


# --- Real repository integration --------------------------------------------


def test_reopen_and_detect_changes_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    loader = RepositoryLoader()

    reopened = loader.reopen(repo_root)  # may or may not be present depending on prior runs
    loaded = loader.load(repo_root)
    assert len(loaded.entries) > 0

    if reopened is not None:
        changes = loader.detect_changes(reopened, loaded)
        # Either it matches exactly (no repo changes since last persist)
        # or reports a real diff — both are valid; it must never error.
        assert isinstance(changes, ChangeSet)
