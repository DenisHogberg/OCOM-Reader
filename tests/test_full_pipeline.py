"""Document -> Adapter -> Normalizer -> OCOMObject -> Storage, end to end."""

from pathlib import Path

from ocom_reader.adapters.filesystem_documentation import FilesystemDocumentationAdapter
from ocom_reader.normalizers.filesystem_documentation_normalizer import (
    FilesystemDocumentationNormalizer,
)
from ocom_reader.storage.local_storage import LocalJSONStorage


def test_full_pipeline_from_document_to_storage(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "object.md").write_text("# Object\n\nAn Object is identifiable.")

    adapter = FilesystemDocumentationAdapter(docs_dir)
    normalizer = FilesystemDocumentationNormalizer()
    storage = LocalJSONStorage(tmp_path / "data")

    for raw in adapter.fetch():
        storage.save(normalizer.normalize(raw))

    [stored] = list(storage.list())
    assert stored.object_type == "Document"
    assert stored.metadata["filename"] == "object.md"
    assert stored.evidence[0].reference == str(docs_dir / "object.md")

    reloaded = storage.get(stored.identity)
    assert reloaded == stored
