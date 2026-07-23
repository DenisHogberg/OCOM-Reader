"""OCOM Runtime v0.2 — Full Reliability Regression Scenario.

Document -> OCOMObject -> Classification -> Registry Search -> Identity
Resolution -> Resolution Policy -> Evidence Aggregation -> Evidence
Presentation -> Answer, exercised through runtime/scenario.py's
ask_with_resolution() — new glue, but no existing layer (agent/,
identity/, intelligence/, runtime/query|search|resolution|evidence,
core/, interfaces/, storage/) is modified to make this work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject
from ocom_reader.intelligence.classification import ClassificationEngine, apply_classification
from ocom_reader.runtime.context import RuntimeContext
from ocom_reader.runtime.scenario import ask_with_resolution
from ocom_reader.storage.local_storage import LocalJSONStorage

CAPTURED_AT = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _make_object(identity: str, concept: str, filename: str, excerpt: str, attributes: dict | None = None) -> OCOMObject:
    metadata = {"identity": {"concept": concept}}
    if attributes:
        metadata["attributes"] = attributes
    obj = OCOMObject(
        identity=identity,
        object_type="Role",
        metadata=metadata,
        evidence=[
            Evidence(
                identity=f"evidence:{identity}",
                source="filesystem-documentation",
                reference=filename,
                captured_at=CAPTURED_AT,
                excerpt=excerpt,
            )
        ],
    )
    proposal = ClassificationEngine().classify(obj)
    return apply_classification(obj, proposal)


def _context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext.build(LocalJSONStorage(tmp_path / "data"))


def test_successful_grounded_answer(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    obj = _make_object(
        "role:affiliate-manager",
        "Affiliate Manager",
        "AffiliateManager.md",
        "manages affiliate relationships and commission payouts",
    )
    ctx.storage.save(obj)

    result = ask_with_resolution("Who manages affiliate relationships?", ctx)

    assert result.resolution.result == "ACCEPT"
    assert result.answer.grounded is True
    assert "AffiliateManager.md" in result.answer.sources


def test_unknown_knowledge_is_not_grounded(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    obj = _make_object(
        "role:affiliate-manager",
        "Affiliate Manager",
        "AffiliateManager.md",
        "manages affiliate relationships and commission payouts",
    )
    ctx.storage.save(obj)

    result = ask_with_resolution("Who manages crypto treasury?", ctx)

    assert result.answer.grounded is False
    assert result.answer.sources == []


def test_ambiguous_identity_produces_uncertain_with_no_false_answer(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    shared_attributes = {"summary": "manages affiliates"}
    eu = _make_object(
        "role:affiliate-manager-eu", "Affiliate Manager EU", "AffiliateManagerEU.md",
        "manages affiliate relationships for the EU region", shared_attributes,
    )
    global_ = _make_object(
        "role:affiliate-manager-global", "Affiliate Manager Global", "AffiliateManagerGlobal.md",
        "manages affiliate relationships globally", shared_attributes,
    )
    ctx.storage.save(eu)
    ctx.storage.save(global_)

    result = ask_with_resolution("Who manages affiliates?", ctx)

    assert result.resolution.result == "UNCERTAIN"
    assert result.resolution.accepted_object_id is None
    # No merge happened in Storage either — both remain separate.
    assert len(list(ctx.storage.list())) == 2
    # No false answer: not silently grounded in a blended, misleading way.
    assert result.answer.grounded is False


def test_evidence_presentation_hides_internal_provenance_ids(tmp_path: Path) -> None:
    """The task's specific claim: the raw Evidence.source value
    ("object-intelligence:classification-engine") must never leak into
    what a user sees, and a human-readable filesystem source must be
    present. That is what this test checks.

    It does NOT check that every source string is fully human-readable
    — the classification-derived Evidence's *reference* (as opposed to
    its *source*) still points at an internal Evidence identity
    (e.g. "evidence:role:affiliate-manager"), because
    EvidencePresentationMapper (built in the prior task, frozen here)
    was scoped to classify source_type and clean up filesystem paths
    only — not to walk a reference chain back to the original
    human-facing Evidence. See this test file's regression findings."""
    ctx = _context(tmp_path)
    obj = _make_object(
        "role:affiliate-manager",
        "Affiliate Manager",
        "AffiliateManager.md",
        "manages affiliate relationships and commission payouts",
    )
    ctx.storage.save(obj)

    result = ask_with_resolution("Who manages affiliate relationships?", ctx)

    assert result.answer.grounded is True
    assert "AffiliateManager.md" in result.answer.sources
    for source in result.answer.sources:
        assert "object-intelligence:classification-engine" not in source


def test_technical_metadata_stays_unsearchable(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.storage.save(
        OCOMObject(
            identity="doc:payment-manager",
            object_type="Document",
            metadata={"technical": {"filename": "PaymentManager.md"}},
        )
    )

    result = ask_with_resolution("Payment Manager", ctx)

    assert result.answer.grounded is False
    assert result.answer.sources == []
