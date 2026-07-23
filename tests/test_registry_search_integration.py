"""Registry Search Integration — QueryNormalizer + SearchPolicy wired into ObjectRegistry.

Registry itself now owns no search logic: no tokenizing, no stopword
handling, no decision about which parts of an object are searchable.
These tests exercise that wiring through ObjectRegistry.find_candidates()
directly — the same entry point runtime/pipeline.py's ask() calls —
rather than re-testing QueryNormalizer or SearchPolicy in isolation
(already covered by their own test files).
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.agent.query import Query
from ocom_reader.agent.registry import ObjectRegistry
from ocom_reader.core.object import OCOMObject
from ocom_reader.storage.local_storage import LocalJSONStorage


def _registry_with(tmp_path: Path, obj: OCOMObject) -> ObjectRegistry:
    storage = LocalJSONStorage(tmp_path / "data")
    storage.save(obj)
    return ObjectRegistry(storage)


def test_no_metadata_key_leakage(tmp_path: Path) -> None:
    obj = OCOMObject(
        identity="role:affiliate-manager",
        object_type="Role",
        metadata={"identity": {"concept": "Affiliate Manager"}},
    )
    registry = _registry_with(tmp_path, obj)

    candidates = registry.find_candidates(Query(text="concept"))

    assert candidates == []


def test_identity_search_works(tmp_path: Path) -> None:
    obj = OCOMObject(
        identity="role:affiliate-manager",
        object_type="Role",
        metadata={"identity": {"concept": "Affiliate Manager"}},
    )
    registry = _registry_with(tmp_path, obj)

    candidates = registry.find_candidates(Query(text="Affiliate Manager"))

    assert candidates == [obj]


def test_technical_metadata_ignored(tmp_path: Path) -> None:
    obj = OCOMObject(
        identity="doc:payment-manager",
        object_type="Document",
        metadata={"technical": {"filename": "PaymentManager.md"}},
    )
    registry = _registry_with(tmp_path, obj)

    candidates = registry.find_candidates(Query(text="Payment Manager"))

    assert candidates == []


def test_attributes_searchable(tmp_path: Path) -> None:
    obj = OCOMObject(
        identity="role:affiliate-manager",
        object_type="Role",
        metadata={"attributes": {"responsibility": "manages affiliate relationships"}},
    )
    registry = _registry_with(tmp_path, obj)

    candidates = registry.find_candidates(Query(text="affiliate"))

    assert candidates == [obj]
