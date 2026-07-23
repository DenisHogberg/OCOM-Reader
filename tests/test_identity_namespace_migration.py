"""ADR-003/ADR-004 implementation — namespace isolation tests.

IdentityResolver now reads only metadata["identity"] (plus the
unchanged object_type/classification fields). These two tests prove
that directly: metadata["attributes"] can carry anything — including
text deliberately chosen to look like the other object's identity —
and it must have zero effect on the decision.

Note: reaching MATCH requires the same combined-score math the
resolver already had (METADATA_WEIGHT=0.6 / CLASSIFICATION_WEIGHT=0.4,
MATCH_THRESHOLD=0.9) — identical metadata["identity"] alone caps the
score at 0.6, so both fixtures below also give matching classification,
the same way MILESTONE-003's original "exact match" fixture did. That
weighting was not touched by this migration and is not touched here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject
from ocom_reader.identity.resolver import IdentityResolver


def _evidence(reference: str, excerpt: str) -> Evidence:
    return Evidence(
        identity=f"evidence:{reference}",
        source="filesystem-documentation",
        reference=reference,
        captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        excerpt=excerpt,
    )


def _object(identity: str, name: str, classification: list[str], attributes_note: str, reference: str) -> OCOMObject:
    return OCOMObject(
        identity=identity,
        object_type="Concept",
        metadata={
            "identity": {"name": name},
            "attributes": {"note": attributes_note},
        },
        classification=classification,
        evidence=[_evidence(reference, attributes_note)],
    )


def test_namespace_isolation_attributes_do_not_affect_a_true_match() -> None:
    a = _object(
        "concept:ocom-object-a", "OCOM Object", ["Meta", "Core"],
        "payment system", "ObjectA.md",
    )
    b = _object(
        "concept:ocom-object-b", "OCOM Object", ["Meta", "Core"],
        "affiliate platform", "ObjectB.md",
    )

    decision = IdentityResolver().resolve(a, b)

    # Same identity name, same classification, wildly different
    # "attributes" content — the resolver must not even look at
    # "attributes", so the mismatch there cannot block the MATCH.
    assert decision.result == "MATCH"
    assert decision.matched_object_id == b.identity


def test_false_match_protection_attributes_cannot_manufacture_a_match() -> None:
    a = _object(
        "concept:affiliate-manager", "Affiliate Manager", [],
        "Payment processing", "AffiliateManager.md",
    )
    b = _object(
        "concept:payment-manager", "Payment Manager", [],
        "Affiliate processing", "PaymentManager.md",
    )

    decision = IdentityResolver().resolve(a, b)

    # The "attributes" text was deliberately swapped so that a resolver
    # still reading it would find a suspiciously strong cross-match
    # ("Affiliate" appears in B's attributes, "Payment" in A's). Because
    # metadata["attributes"] is never read, this has no effect: the
    # decision rests only on the genuinely different identity names.
    assert decision.result != "MATCH"
    assert decision.matched_object_id is None
