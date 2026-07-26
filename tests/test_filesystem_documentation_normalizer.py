import hashlib
from pathlib import Path

from ocom_reader.adapters.filesystem_documentation import (
    FilesystemDocumentationAdapter,
    to_memory_entry,
)
from ocom_reader.core.object import OCOMObject
from ocom_reader.normalizers.filesystem_documentation_normalizer import (
    FilesystemDocumentationNormalizer,
)


def _fetch_one(tmp_path: Path, name: str, content: str):
    """Returns a MemoryEntry, not a raw RawDocument — every existing test
    below normalizes what it gets back exactly as before; only the type
    flowing through this helper changed, per ADR-007."""
    (tmp_path / name).write_text(content)
    [record] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    return to_memory_entry(record)


def test_normalize_returns_ocom_object(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Title\n\nBody")

    obj = FilesystemDocumentationNormalizer().normalize(record)

    assert isinstance(obj, OCOMObject)
    assert obj.object_type == "Document"
    assert obj.metadata == {
        "technical": {
            "filename": "a.md",
            "extension": ".md",
            "size_bytes": record.metadata["size_bytes"],
            "content_length": len("# Title\n\nBody"),
        },
    }


def test_identity_is_stable_across_calls_and_content_changes(tmp_path: Path) -> None:
    normalizer = FilesystemDocumentationNormalizer()

    record_v1 = _fetch_one(tmp_path, "a.md", "first version")
    identity_v1 = normalizer.normalize(record_v1).identity

    (tmp_path / "a.md").write_text("second version, same path")
    [record_v2] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    identity_v2 = normalizer.normalize(to_memory_entry(record_v2)).identity

    assert identity_v1 == identity_v2


def test_identity_differs_across_files(tmp_path: Path) -> None:
    normalizer = FilesystemDocumentationNormalizer()

    (tmp_path / "a.md").write_text("A")
    (tmp_path / "b.md").write_text("B")
    a, b = list(FilesystemDocumentationAdapter(tmp_path).fetch())

    assert (
        normalizer.normalize(to_memory_entry(a)).identity
        != normalizer.normalize(to_memory_entry(b)).identity
    )


def test_evidence_points_back_to_the_source_document(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Title\n\nBody")

    obj = FilesystemDocumentationNormalizer().normalize(record)

    [evidence] = obj.evidence
    assert evidence.source == "filesystem-documentation"
    assert evidence.reference == record.source_identifier
    assert evidence.captured_at == record.timestamp
    assert evidence.excerpt == "# Title\n\nBody"


def test_identity_and_evidence_reference_unchanged_by_memory_entry_migration(
    tmp_path: Path,
) -> None:
    """M021 Phase 1 regression: promoting RawDocument to MemoryEntry must not
    change OCOMObject.identity or Evidence.reference for the same file.

    Independently pins the exact pre-migration algorithm (sha256 of the
    *resolved* path, truncated to 16 hex chars, for identity; the
    *unresolved* `str(path)` for evidence.reference) so a future refactor
    cannot silently drift from it.
    """
    (tmp_path / "a.md").write_text("content")
    [raw] = list(FilesystemDocumentationAdapter(tmp_path).fetch())

    expected_digest = hashlib.sha256(
        str((tmp_path / "a.md").resolve()).encode("utf-8")
    ).hexdigest()
    expected_identity = f"fsdoc:{expected_digest[:16]}"
    expected_reference = str(raw.path)

    obj = FilesystemDocumentationNormalizer().normalize(to_memory_entry(raw))

    assert obj.identity == expected_identity
    assert obj.evidence[0].reference == expected_reference
