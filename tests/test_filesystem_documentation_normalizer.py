from pathlib import Path

from ocom_reader.adapters.filesystem_documentation import FilesystemDocumentationAdapter
from ocom_reader.core.object import OCOMObject
from ocom_reader.normalizers.filesystem_documentation_normalizer import (
    FilesystemDocumentationNormalizer,
)


def _fetch_one(tmp_path: Path, name: str, content: str):
    (tmp_path / name).write_text(content)
    [record] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    return record


def test_normalize_returns_ocom_object(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Title\n\nBody")

    obj = FilesystemDocumentationNormalizer().normalize(record)

    assert isinstance(obj, OCOMObject)
    assert obj.object_type == "Document"
    assert obj.metadata == {
        "filename": "a.md",
        "extension": ".md",
        "size_bytes": record.metadata["size_bytes"],
        "content_length": len("# Title\n\nBody"),
    }


def test_identity_is_stable_across_calls_and_content_changes(tmp_path: Path) -> None:
    normalizer = FilesystemDocumentationNormalizer()

    record_v1 = _fetch_one(tmp_path, "a.md", "first version")
    identity_v1 = normalizer.normalize(record_v1).identity

    (tmp_path / "a.md").write_text("second version, same path")
    [record_v2] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    identity_v2 = normalizer.normalize(record_v2).identity

    assert identity_v1 == identity_v2


def test_identity_differs_across_files(tmp_path: Path) -> None:
    normalizer = FilesystemDocumentationNormalizer()

    (tmp_path / "a.md").write_text("A")
    (tmp_path / "b.md").write_text("B")
    a, b = list(FilesystemDocumentationAdapter(tmp_path).fetch())

    assert normalizer.normalize(a).identity != normalizer.normalize(b).identity


def test_evidence_points_back_to_the_source_document(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Title\n\nBody")

    obj = FilesystemDocumentationNormalizer().normalize(record)

    [evidence] = obj.evidence
    assert evidence.source == "filesystem-documentation"
    assert evidence.reference == str(record.path)
    assert evidence.captured_at == record.modified_at
    assert evidence.excerpt == "# Title\n\nBody"
