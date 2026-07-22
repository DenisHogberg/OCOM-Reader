from pathlib import Path

from ocom_reader.adapters.filesystem_documentation import FilesystemDocumentationAdapter


def test_fetch_returns_only_supported_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "b.txt").write_text("plain text")
    (tmp_path / "c.png").write_bytes(b"\x89PNG")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "d.md").write_text("# D")

    adapter = FilesystemDocumentationAdapter(tmp_path)
    records = list(adapter.fetch())

    paths = sorted(r.path.name for r in records)
    assert paths == ["a.md", "b.txt", "d.md"]


def test_fetch_returns_raw_content_and_basic_metadata(tmp_path: Path) -> None:
    doc = tmp_path / "a.md"
    doc.write_text("# Title\n\nBody")

    adapter = FilesystemDocumentationAdapter(tmp_path)
    [record] = list(adapter.fetch())

    assert record.path == doc
    assert record.content == "# Title\n\nBody"
    assert record.modified_at is not None
    assert record.metadata == {
        "filename": "a.md",
        "extension": ".md",
        "size_bytes": doc.stat().st_size,
    }
