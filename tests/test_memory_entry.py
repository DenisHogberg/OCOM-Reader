"""MemoryEntry / MemoryStore — the new architectural boundary from ADR-007.

Two kinds of coverage: MemoryEntry/LocalJSONMemoryStore in isolation
(mirroring test_local_storage.py's own coverage of Storage), and one
integration test that proves the actual point of ADR-007 — Knowledge is
fully recomputable from persisted Memory, not from the original
in-memory object or the source file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ocom_reader.adapters.filesystem_documentation import (
    FilesystemDocumentationAdapter,
    to_memory_entry,
)
from ocom_reader.core.memory import MemoryEntry, content_hash
from ocom_reader.normalizers.filesystem_documentation_normalizer import (
    FilesystemDocumentationNormalizer,
)
from ocom_reader.storage.local_memory_store import LocalJSONMemoryStore


def test_id_is_a_full_content_hash_independent_of_location(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("same content")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("same content")

    a, b = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    entry_a, entry_b = to_memory_entry(a), to_memory_entry(b)

    assert entry_a.id == entry_b.id == content_hash("same content")
    assert len(entry_a.id) == 64  # full SHA-256 hex digest, never truncated


def test_memory_entry_is_immutable(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("content")
    [raw] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    entry = to_memory_entry(raw)

    with pytest.raises(ValidationError):
        entry.raw_content = "tampered"


def test_local_memory_store_save_get_list_delete_roundtrip(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("content")
    [raw] = list(FilesystemDocumentationAdapter(tmp_path / "docs").fetch())
    entry = to_memory_entry(raw)

    store = LocalJSONMemoryStore(tmp_path / "memory")
    store.save(entry)

    loaded = store.get(entry.id)
    assert loaded == entry

    assert [e.id for e in store.list()] == [entry.id]

    store.delete(entry.id)
    assert store.get(entry.id) is None
    assert list(store.list()) == []


def test_knowledge_is_fully_recomputable_from_persisted_memory(tmp_path: Path) -> None:
    """The actual claim ADR-007 makes: re-deriving an OCOMObject from a
    MemoryEntry reloaded purely from MemoryStore — with no reference to
    the original in-memory object or the source file — produces the
    identical result to normalizing the freshly-fetched one. This is the
    new architectural boundary; a plain JSON round-trip alone would not
    prove it."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "object.md").write_text("# Object\n\nAn Object is identifiable.")

    adapter = FilesystemDocumentationAdapter(docs_dir)
    normalizer = FilesystemDocumentationNormalizer()
    memory_store = LocalJSONMemoryStore(tmp_path / "memory")

    [raw] = list(adapter.fetch())
    memory_entry = to_memory_entry(raw)
    memory_store.save(memory_entry)

    direct = normalizer.normalize(memory_entry)

    # Reload from the store only — no `raw`, no `memory_entry`, no filesystem.
    reloaded_entry = memory_store.get(memory_entry.id)
    assert reloaded_entry is not None
    reconstructed = normalizer.normalize(reloaded_entry)

    assert reconstructed == direct
