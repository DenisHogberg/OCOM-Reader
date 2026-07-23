"""SearchPolicy v0.1.

Standalone: not wired into Registry or the runtime pipeline. Matching
in these tests is done by reusing the already-built QueryNormalizer
(same "any token present" semantics as agent/registry.py) directly
against SearchPolicy.searchable_text() output — proving the two
compose correctly without either depending on the other.
"""

from __future__ import annotations

from ocom_reader.core.object import OCOMObject
from ocom_reader.runtime.query.normalizer import QueryNormalizer
from ocom_reader.runtime.search.policy import SearchPolicy


def _object(metadata: dict, object_type: str = "Role", classification: list[str] | None = None) -> OCOMObject:
    return OCOMObject(
        identity="test:object",
        object_type=object_type,
        metadata=metadata,
        classification=classification or [],
    )


def _matches(obj: OCOMObject, query: str) -> bool:
    text = SearchPolicy().searchable_text(obj)
    tokens = QueryNormalizer().normalize(query).tokens
    return any(token in text for token in tokens)


def test_metadata_key_names_are_not_searchable() -> None:
    obj = _object(
        metadata={
            "identity": {"concept": "Affiliate Manager"},
            "technical": {"source": "concept.md"},
        }
    )

    assert _matches(obj, "concept") is False


def test_identity_values_are_searchable() -> None:
    obj = _object(
        metadata={
            "identity": {"concept": "Affiliate Manager"},
            "technical": {"source": "concept.md"},
        }
    )

    assert _matches(obj, "Affiliate Manager") is True


def test_technical_namespace_is_entirely_excluded() -> None:
    obj = _object(metadata={"technical": {"filename": "PaymentManager.md"}})

    assert _matches(obj, "Payment Manager") is False


def test_attributes_values_are_searchable() -> None:
    obj = _object(metadata={"attributes": {"responsibility": "manages affiliate relationships"}})

    assert _matches(obj, "affiliate") is True


def test_attributes_provenance_fields_are_excluded_even_when_nested() -> None:
    """The real shape ClassificationEngine writes
    (metadata["attributes"]["classification"] = [{...}]) nests
    evidence/confidence/timestamp inside list items, not just at the
    top level of "attributes" — this must still be excluded there."""
    obj = _object(
        metadata={
            "attributes": {
                "classification": [
                    {
                        "domain": "Marketing",
                        "category": "Partner Management",
                        "type": "Role",
                        "evidence": ["evidence:oi-classification-affiliate-manager-01"],
                        "confidence": "Medium",
                        "timestamp": "2026-07-23T00:00:00Z",
                    }
                ]
            }
        }
    )

    text = SearchPolicy().searchable_text(obj)

    assert "marketing" in text
    assert "partner management" in text
    assert "oi-classification-affiliate-manager-01" not in text
    assert "medium" not in text
    assert "2026-07-23" not in text
