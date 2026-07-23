"""OCOM Identity Resolution — Object Representation Experiment.

Question: is IdentityResolver v0.1's problem that the algorithm isn't
smart enough (A), or that OCOMObject wasn't given enough information
to work with (B)?

The resolver (identity/resolver.py) is used completely unmodified in
every case here — only the OCOMObject input changes, across three
representations of the same two role pairs:

  Variant A  — minimal: identity, object_type, metadata["name"] only.
  Variant B' — structured enrichment: + classification, relationships,
               lifecycle_state, evidence. No free-text attribute.
  Variant B  — Variant B' + a free-text "responsibility" attribute in
               metadata (as in the task's own example).

Two pairs, tested identically across all three variants:
  - Affiliate Manager / Partner Manager  (related roles, plausibly similar)
  - Affiliate Manager / Payment Manager  (unrelated roles, clearly different)

A resolver with enough signal should treat these two pairs differently.
See the chat write-up accompanying this experiment for the verdict.

Fixtures use the namespaced metadata shape decided in
docs/architecture/ADR-003-metadata-semantic-boundary.md and
docs/architecture/ADR-004-metadata-namespace-migration.md
(`metadata["identity"]` / `metadata["attributes"]`) — the resolver
reads only `metadata["identity"]`. `test_freetext_attribute_...` below
was updated accordingly: it now demonstrates the fix rather than the
bug it originally found.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject, Relationship
from ocom_reader.identity.resolver import IdentityResolver


def _evidence(reference: str, excerpt: str) -> Evidence:
    return Evidence(
        identity=f"evidence:{reference}",
        source="filesystem-documentation",
        reference=reference,
        captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        excerpt=excerpt,
    )


def _variant_a(identity: str, name: str) -> OCOMObject:
    """Minimal: id, type, metadata["identity"]["name"] only — nothing else populated."""
    return OCOMObject(identity=identity, object_type="Role", metadata={"identity": {"name": name}})


def _variant_b_structured(identity: str, name: str, classification: list[str], related_to: str, reference: str) -> OCOMObject:
    """Enriched, but no free-text attribute: classification, relationships,
    lifecycle_state, evidence — every field the resolver can read except
    unstructured text."""
    return OCOMObject(
        identity=identity,
        object_type="Role",
        metadata={"identity": {"name": name}},
        classification=classification,
        relationships=[Relationship(target_id=related_to, relationship_type="collaborates_with")],
        lifecycle_state="active",
        evidence=[_evidence(reference, f"{name} role definition")],
    )


def _variant_b_freetext(identity: str, name: str, classification: list[str], responsibility: str, related_to: str, reference: str) -> OCOMObject:
    """Variant B' plus a free-text "responsibility" attribute — now placed
    under metadata["attributes"], per ADR-003/ADR-004, since free text is
    forbidden in metadata["identity"]. The resolver never reads
    "attributes" at all, so this data can no longer influence a decision
    regardless of wording."""
    return OCOMObject(
        identity=identity,
        object_type="Role",
        metadata={"identity": {"name": name}, "attributes": {"responsibility": responsibility}},
        classification=classification,
        relationships=[Relationship(target_id=related_to, relationship_type="collaborates_with")],
        lifecycle_state="active",
        evidence=[_evidence(reference, responsibility)],
    )


def test_variant_a_minimal_cannot_distinguish_the_two_pairs() -> None:
    resolver = IdentityResolver()
    affiliate = _variant_a("role:affiliate-a", "Affiliate Manager")
    partner = _variant_a("role:partner-a", "Partner Manager")
    payment = _variant_a("role:payment-a", "Payment Manager")

    affiliate_vs_partner = resolver.resolve(affiliate, partner)
    affiliate_vs_payment = resolver.resolve(affiliate, payment)

    # Both come out the same way, for the same underlying reason: a bare
    # name gives the resolver no way to tell "related role" from
    # "unrelated role" apart — confirmed, not assumed.
    assert affiliate_vs_partner.result == "NEW"
    assert affiliate_vs_payment.result == "NEW"
    assert affiliate_vs_partner.reasoning == affiliate_vs_payment.reasoning


def test_structured_enrichment_alone_distinguishes_the_two_pairs() -> None:
    resolver = IdentityResolver()
    affiliate = _variant_b_structured(
        "role:affiliate-b1", "Affiliate Manager", ["Marketing", "Partner Management"],
        "role:partner-b1", "AffiliateManager.md",
    )
    partner = _variant_b_structured(
        "role:partner-b1", "Partner Manager", ["Marketing", "Partner Management"],
        "role:affiliate-b1", "PartnerManager.md",
    )
    payment = _variant_b_structured(
        "role:payment-b1", "Payment Manager", ["Finance", "Payments"],
        "role:wallet-b1", "PaymentManager.md",
    )

    affiliate_vs_partner = resolver.resolve(affiliate, partner)
    affiliate_vs_payment = resolver.resolve(affiliate, payment)

    # Same resolver code as the test above. The only thing that changed
    # is that classification (and the rest of Variant B') is now
    # populated. That alone is enough to tell the two pairs apart.
    assert affiliate_vs_partner.result == "UNCERTAIN"
    assert affiliate_vs_payment.result == "NEW"


def test_freetext_attribute_no_longer_affects_the_score() -> None:
    """Originally (pre-ADR-003/004) this test proved the opposite: two
    equally plausible phrasings of the same free-text attribute produced
    different outcomes, including a false MATCH. Now that the resolver
    reads only metadata["identity"] and free text lives in
    metadata["attributes"] instead, both phrasings must produce the same
    result — proving the wording-sensitivity bug is actually closed, not
    just moved."""
    resolver = IdentityResolver()

    # Phrasing 1: natural, independently-written descriptions.
    affiliate_1 = _variant_b_freetext(
        "role:affiliate-b2", "Affiliate Manager", ["Marketing", "Partner Management"],
        "tracks affiliate performance and approves commission payouts",
        "role:partner-b2", "AffiliateManager.md",
    )
    partner_1 = _variant_b_freetext(
        "role:partner-b2", "Partner Manager", ["Marketing", "Partner Management"],
        "negotiates partnership terms and onboards new strategic partners",
        "role:affiliate-b2", "PartnerManager.md",
    )
    result_1 = resolver.resolve(affiliate_1, partner_1)

    # Phrasing 2: each description happens to mention the other role by
    # name — this is exactly the wording that used to flip the outcome
    # to a false MATCH before this migration.
    affiliate_2 = _variant_b_freetext(
        "role:affiliate-b3", "Affiliate Manager", ["Marketing", "Partner Management"],
        "manages affiliate relationships and partner recruitment",
        "role:partner-b3", "AffiliateManager.md",
    )
    partner_2 = _variant_b_freetext(
        "role:partner-b3", "Partner Manager", ["Marketing", "Partner Management"],
        "manages partner relationships and affiliate recruitment",
        "role:affiliate-b3", "PartnerManager.md",
    )
    result_2 = resolver.resolve(affiliate_2, partner_2)

    assert result_1.result == result_2.result == "UNCERTAIN"
    assert result_1.reasoning == result_2.reasoning
