"""EvidencePresentationMapper v0.1.

Standalone, read-only: no Storage, no OCOMObject construction, no
mutation of the Evidence it reads.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ocom_reader.core.evidence import Evidence
from ocom_reader.runtime.evidence.mapper import EvidencePresentationMapper

CAPTURED_AT = datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_filesystem_evidence_maps_to_filesystem_source_type_and_basename() -> None:
    evidence = Evidence(
        identity="evidence:fsdoc:a82c91",
        source="filesystem-documentation",
        reference="/docs/AffiliateManager.md",
        captured_at=CAPTURED_AT,
        excerpt="Responsible for affiliate relationships",
    )

    view = EvidencePresentationMapper().to_view(evidence)

    assert view.source_type == "filesystem"
    assert view.reference == "AffiliateManager.md"
    assert view.excerpt == "Responsible for affiliate relationships"
    assert view.original_id == "evidence:fsdoc:a82c91"


def test_object_intelligence_evidence_maps_to_object_intelligence_source_type() -> None:
    evidence = Evidence(
        identity="evidence:oi-classification-123",
        source="object-intelligence:classification",
        reference="object:123",
        captured_at=CAPTURED_AT,
        excerpt="Detected Role classification",
    )

    view = EvidencePresentationMapper().to_view(evidence)

    assert view.source_type == "object-intelligence"
    assert view.reference == "object:123"


def test_unknown_source_is_classified_external_without_guessing() -> None:
    evidence = Evidence(
        identity="evidence:external-1",
        source="external-api",
        reference="https://example.com/records/1",
        captured_at=CAPTURED_AT,
    )

    view = EvidencePresentationMapper().to_view(evidence)

    assert view.source_type == "external"
    assert view.reference == "https://example.com/records/1"  # unchanged, not parsed


def test_original_evidence_is_left_unmodified() -> None:
    evidence = Evidence(
        identity="evidence:fsdoc:a82c91",
        source="filesystem-documentation",
        reference="/docs/AffiliateManager.md",
        captured_at=CAPTURED_AT,
        excerpt="Responsible for affiliate relationships",
    )
    reference_before = evidence.reference

    EvidencePresentationMapper().to_view(evidence)

    assert evidence.reference == reference_before
    assert evidence.reference == "/docs/AffiliateManager.md"
