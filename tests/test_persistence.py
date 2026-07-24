"""Persistent Storage v0.1 (M012).

Most scenarios use a small, synthetic repository (tmp_path). The
real-repository section (bottom) uses only this project's own
repository, matching the portability discipline every prior
milestone's integration test used.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ocom_reader.indexer import RepositoryIndexBuilder
from ocom_reader.persistence import CURRENT_STORAGE_VERSION, PersistentStore
from ocom_reader.persistence.migrations import MIGRATIONS, migrate_to_current
from ocom_reader.persistence.models import MigrationError
from ocom_reader.registry import RegistryBuilder


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build(root: Path):
    index = RepositoryIndexBuilder(root).build()
    registry = RegistryBuilder().build(index)
    return index, registry


# --- Layout -----------------------------------------------------------------


def test_ocom_dir_is_created_inside_the_repository(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)

    PersistentStore(tmp_path).save(index, registry)

    ocom_dir = tmp_path / ".ocom"
    assert ocom_dir.is_dir()
    assert {p.name for p in ocom_dir.iterdir()} == {"metadata.json", "index.json", "registry.json", "retrieval.json"}


def test_exists_is_false_before_any_save(tmp_path: Path) -> None:
    assert PersistentStore(tmp_path).exists() is False


def test_exists_is_true_after_save(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)

    assert store.exists() is True


# --- Round-trip ---------------------------------------------------------------


def test_index_round_trips_exactly(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\n## Heading\n\nBody with a [link](b.md).")
    _write(tmp_path, "docs/b.md", "# B\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)
    loaded = store.load_index()

    assert loaded is not None
    assert loaded.model_dump() == index.model_dump()


def test_registry_round_trips_exactly(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    _write(tmp_path, "docs/b.md", "# B\n\n**Builds on:** [A](a.md)\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)
    loaded = store.load_registry()

    assert loaded is not None
    assert loaded.model_dump() == registry.model_dump()


def test_retrieval_metadata_defaults_to_a_ranking_config_placeholder(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)

    assert store.load_retrieval_metadata() == {"ranking_config": {}}


def test_retrieval_metadata_is_empty_dict_before_any_save(tmp_path: Path) -> None:
    assert PersistentStore(tmp_path).load_retrieval_metadata() == {}


# --- metadata.json -----------------------------------------------------------


def test_metadata_has_the_required_fields(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)
    metadata = store.load_metadata()

    assert metadata.storage_version == CURRENT_STORAGE_VERSION
    assert metadata.reader_version
    assert metadata.repository_root == str(tmp_path.resolve())
    assert metadata.created_at is not None
    assert metadata.last_updated is not None


def test_created_at_is_stable_across_resaves_but_last_updated_advances(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)
    first = store.load_metadata()

    time.sleep(0.01)
    store.save(index, registry)
    second = store.load_metadata()

    assert first.created_at == second.created_at
    assert second.last_updated > first.last_updated


def test_load_metadata_is_none_before_any_save(tmp_path: Path) -> None:
    assert PersistentStore(tmp_path).load_metadata() is None


# --- Compatibility -----------------------------------------------------------


def test_compatibility_false_with_nothing_stored(tmp_path: Path) -> None:
    compat = PersistentStore(tmp_path).check_compatibility()

    assert compat.compatible is False
    assert compat.stored_version is None
    assert compat.current_version == CURRENT_STORAGE_VERSION


def test_compatibility_true_after_a_normal_save(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)

    store.save(index, registry)
    compat = store.check_compatibility()

    assert compat.compatible is True
    assert compat.stored_version == CURRENT_STORAGE_VERSION


def test_a_newer_stored_version_is_incompatible(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    store = PersistentStore(tmp_path)
    store.save(index, registry)

    import json

    from ocom_reader.persistence import paths

    envelope = json.loads(paths.metadata_path(tmp_path).read_text())
    envelope["storage_version"] = CURRENT_STORAGE_VERSION + 1
    paths.metadata_path(tmp_path).write_text(json.dumps(envelope))

    compat = store.check_compatibility()

    assert compat.compatible is False
    assert compat.stored_version == CURRENT_STORAGE_VERSION + 1


# --- Migration scaffold --------------------------------------------------------


def test_migrate_to_current_chains_registered_migrations() -> None:
    def upgrade_0_to_1(data: dict) -> dict:
        data = dict(data)
        data["migrated_from_0"] = True
        return data

    MIGRATIONS[0] = upgrade_0_to_1
    try:
        result = migrate_to_current({"entries": []}, from_version=0)
    finally:
        MIGRATIONS.clear()

    assert result == {"entries": [], "migrated_from_0": True}


def test_migrate_to_current_with_no_migration_needed_is_a_no_op() -> None:
    assert migrate_to_current({"x": 1}, from_version=CURRENT_STORAGE_VERSION) == {"x": 1}


def test_migrate_to_current_raises_when_no_migration_is_registered() -> None:
    with pytest.raises(MigrationError):
        migrate_to_current({}, from_version=0)


# --- Safety: never writes outside the repository -------------------------------


def test_store_never_writes_outside_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(repo)

    PersistentStore(repo).save(index, registry)

    assert not (tmp_path / ".ocom").exists()  # only repo/.ocom, not tmp_path/.ocom
    assert (repo / ".ocom").exists()


def test_store_does_not_mutate_the_index_or_registry_it_saves(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# A\n\nBody.")
    index, registry = _build(tmp_path)
    index_before = index.model_dump()
    registry_before = registry.model_dump()

    PersistentStore(tmp_path).save(index, registry)

    assert index.model_dump() == index_before
    assert registry.model_dump() == registry_before


# --- Real repository integration --------------------------------------------


def test_persistent_store_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    store = PersistentStore(repo_root)

    index = RepositoryIndexBuilder(repo_root).build()
    registry = RegistryBuilder().build(index)
    store.save(index, registry)

    assert store.exists() is True
    loaded_index = store.load_index()
    loaded_registry = store.load_registry()
    assert loaded_index.model_dump() == index.model_dump()
    assert loaded_registry.model_dump() == registry.model_dump()

    compat = store.check_compatibility()
    assert compat.compatible is True
