from datetime import datetime, timezone
from pathlib import Path

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject, Relationship
from ocom_reader.storage.local_storage import LocalJSONStorage


def test_save_get_list_delete_roundtrip(tmp_path: Path) -> None:
    storage = LocalJSONStorage(tmp_path)

    obj = OCOMObject(
        identity="doc-001",
        object_type="Document",
        metadata={"title": "Object"},
        classification=["Meta"],
        relationships=[Relationship(target_id="doc-002", relationship_type="references")],
        lifecycle_state="draft",
        owner="ocom-core-team",
        governance={"status": "Draft"},
        evidence=[
            Evidence(
                identity="ev-001",
                source="ocom-documentation",
                reference="Meta/Object.md.docx",
                captured_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
                excerpt="An Object is an identifiable and governable element...",
            )
        ],
    )

    storage.save(obj)

    loaded = storage.get("doc-001")
    assert loaded == obj

    assert [o.identity for o in storage.list()] == ["doc-001"]

    storage.delete("doc-001")
    assert storage.get("doc-001") is None
    assert list(storage.list()) == []
