"""IdentityResolver v0.1 — validation experiment.

Standalone: proves the rule-based decision model against real OCOM
Reader object shapes before it is wired into agent/ or Storage. See
docs/architecture/OCOM-Identity-Resolution-v0.1.md for the design this
implements, and the chat write-up accompanying this experiment for
where it holds and where it breaks.

Fixtures use the namespaced metadata shape decided in
docs/architecture/ADR-003-metadata-semantic-boundary.md and
docs/architecture/ADR-004-metadata-namespace-migration.md
(`metadata["identity"]`) — the resolver no longer reads flat metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject
from ocom_reader.identity.resolver import IdentityResolver

EVIDENCE = Evidence(
    identity="evidence:fixture",
    source="filesystem-documentation",
    reference="fixture.md",
    captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    excerpt="fixture excerpt",
)


def _concept(identity: str, name: str, classification: list[str], with_evidence: bool = True) -> OCOMObject:
    return OCOMObject(
        identity=identity,
        object_type="Concept",
        metadata={"identity": {"name": name}},
        classification=classification,
        evidence=[EVIDENCE] if with_evidence else [],
    )


def test_exact_match() -> None:
    a = _concept("concept:ocom-object-a", "OCOM Object", ["Meta", "Core"])
    b = _concept("concept:ocom-object-b", "OCOM Object", ["Meta", "Core"])

    decision = IdentityResolver().resolve(a, b)

    assert decision.result == "MATCH"
    assert decision.matched_object_id == b.identity


def test_different_objects() -> None:
    a = _concept("concept:ocom-object", "OCOM Object", ["Meta", "Core"])
    b = _concept("concept:payment-object", "Payment Object", ["Payments", "Entity"])

    decision = IdentityResolver().resolve(a, b)

    assert decision.result == "NEW"
    assert decision.matched_object_id is None


def test_ambiguous_similar_objects() -> None:
    a = _concept("concept:affiliate-manager", "Affiliate Manager", ["Role", "CRM"])
    b = _concept("concept:partner-manager", "Partner Manager", ["Role", "CRM"])

    decision = IdentityResolver().resolve(a, b)

    assert decision.result == "UNCERTAIN"
    assert decision.matched_object_id is None


def test_no_match_without_evidence() -> None:
    a = _concept("concept:ocom-object-a", "OCOM Object", ["Meta", "Core"], with_evidence=False)
    b = _concept("concept:ocom-object-b", "OCOM Object", ["Meta", "Core"], with_evidence=True)

    decision = IdentityResolver().resolve(a, b)

    assert decision.result != "MATCH"
    assert decision.matched_object_id is None
    assert "evidence" in decision.reasoning.lower()
