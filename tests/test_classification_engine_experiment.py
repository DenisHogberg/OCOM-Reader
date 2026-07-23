"""Classification Engine v0.1 — Validation Experiment.

Not testing whether rule-based classification is "good" — testing
where the boundary sits between Dictionary/known-vocabulary and
Semantic-understanding/LLM. See
docs/architecture/OCOM-Classification-Engine-v0.1.md for the design
this implements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject
from ocom_reader.intelligence.classification import ClassificationEngine, apply_classification


def _role(name: str, excerpt: str = "") -> OCOMObject:
    evidence = []
    if excerpt:
        evidence = [
            Evidence(
                identity=f"evidence:{name}",
                source="filesystem-documentation",
                reference=f"{name.replace(' ', '')}.md",
                captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
                excerpt=excerpt,
            )
        ]
    return OCOMObject(
        identity=f"role:{name.lower().replace(' ', '-')}",
        object_type="Role",
        metadata={"identity": {"name": name}},
        evidence=evidence,
    )


def test_known_concept_produces_the_full_expected_classification() -> None:
    obj = _role("Affiliate Manager", "manages affiliate relationships and commission payouts")

    proposal = ClassificationEngine().classify(obj)

    assert set(proposal.flat_tags) == {"Role", "Marketing", "Partner Management"}
    assert proposal.confidence == "Medium"


def test_semantic_neighbour_produces_only_a_partial_classification() -> None:
    """"Partner Success Lead" is plausibly the same kind of role as
    "Affiliate Manager" to a human. The dictionary only catches the
    literal word "partner" — it has no notion that "Lead" and "Manager"
    name the same kind of thing, and no domain rule fires at all
    without "affiliate" or "payment" present. This is the experiment's
    answer to "can rule-based understand a close meaning?": only via
    literal overlap, not generalization."""
    obj = _role("Partner Success Lead")

    proposal = ClassificationEngine().classify(obj)

    assert proposal.category == "Partner Management"  # literal "partner" overlap
    assert proposal.domain is None                      # no "affiliate"/"payment" present
    assert proposal.type is None                         # name doesn't end in "Manager"
    assert not proposal.is_empty                          # partial, not "Unknown"


def test_false_positive_protection_payment_manager_is_not_partner_management() -> None:
    obj = _role("Payment Manager")

    proposal = ClassificationEngine().classify(obj)

    assert proposal.category != "Partner Management"
    assert proposal.domain == "Finance"
    assert proposal.category == "Payment Processing"
    assert proposal.type == "Role"


def test_no_recognized_vocabulary_produces_no_classification_at_all() -> None:
    """A name with none of the dictionary's words produces nothing —
    an honest gap, not a fabricated guess."""
    obj = _role("Widget")

    proposal = ClassificationEngine().classify(obj)

    assert proposal.is_empty
    assert proposal.confidence is None


def test_evidence_propagation_when_classification_is_applied() -> None:
    obj = _role("Affiliate Manager", "manages affiliate relationships and commission payouts")
    proposal = ClassificationEngine().classify(obj)

    enriched = apply_classification(obj, proposal)

    # Original object is untouched (Object Intelligence never mutates in place).
    assert len(obj.evidence) == 1
    assert enriched is not obj

    assert set(enriched.classification) == {"Role", "Marketing", "Partner Management"}

    assert len(enriched.evidence) == len(obj.evidence) + 1
    new_evidence = enriched.evidence[-1]
    assert new_evidence.source == "object-intelligence:classification-engine"
    assert new_evidence.excerpt != ""
    assert new_evidence.captured_at is not None
    assert new_evidence.reference == obj.evidence[0].identity  # chains back to the upstream Evidence

    [record] = enriched.metadata["attributes"]["classification"]
    assert record["confidence"] == "Medium"
    assert record["timestamp"] is not None
    assert record["evidence"] == [new_evidence.identity]


def test_apply_classification_is_a_noop_when_nothing_matched() -> None:
    obj = _role("Widget")
    proposal = ClassificationEngine().classify(obj)

    result = apply_classification(obj, proposal)

    assert result == obj
