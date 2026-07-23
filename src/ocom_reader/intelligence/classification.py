"""Classification Engine v0.1 — rule-based, stdlib only.

Standalone validation experiment for
docs/architecture/OCOM-Classification-Engine-v0.1.md. Not wired into
Normalizers, Agent, or IdentityResolver — this proves the Option A
(rule-based dictionary) decision against concrete cases before any
real integration is built.

Produces two things from one OCOMObject, per the Classification Model
already specified: a flat tag list (what would go into the existing
`OCOMObject.classification: list[str]`, unchanged) and a structured
record (what would go into `metadata["attributes"]["classification"]`),
backed by a new Evidence entry on the existing `evidence` list.

Reads metadata["identity"] *and* Evidence excerpts as input vocabulary
— deliberately different from IdentityResolver, which is restricted to
metadata["identity"] only (ADR-003/ADR-005). This component matches
free text against a fixed dictionary, not against another object's
free text, so it does not carry the pairwise-comparison contamination
risk MILESTONE-003 found.

The dictionary is deliberately small (four rules). It is not tuned to
pass every test in this experiment — see the accompanying test file
and docs/architecture/OCOM-Classification-Engine-v0.1.md for which
outcomes were expected to be partial or absent.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject

SOURCE_NAME = "object-intelligence:classification-engine"

# keyword -> proposed domain/category. Deliberately small — see
# docs/architecture/OCOM-Classification-Engine-v0.1.md "Where rule-based
# breaks" for why this is not meant to grow into a general-purpose
# taxonomy.
KEYWORD_RULES: dict[str, dict[str, str]] = {
    "affiliate": {"domain": "Marketing", "category": "Partner Management"},
    "partner": {"category": "Partner Management"},
    "payment": {"domain": "Finance", "category": "Payment Processing"},
}

# last word of the object's name -> proposed type.
TYPE_SUFFIX_RULES: dict[str, str] = {
    "manager": "Role",
}


class ClassificationProposal(BaseModel):
    domain: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    matched_keywords: list[str] = Field(default_factory=list)
    confidence: Optional[str] = None  # None when nothing matched at all

    @property
    def flat_tags(self) -> list[str]:
        ordered: list[str] = []
        for value in (self.type, self.domain, self.category):
            if value and value not in ordered:
                ordered.append(value)
        return ordered

    @property
    def is_empty(self) -> bool:
        return not (self.domain or self.category or self.type)


def _tokenize(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _identity_name(obj: OCOMObject) -> str:
    identity_ns = obj.metadata.get("identity")
    if not isinstance(identity_ns, dict):
        return ""
    return str(identity_ns.get("name") or identity_ns.get("concept") or "")


class ClassificationEngine:
    def classify(self, obj: OCOMObject) -> ClassificationProposal:
        name = _identity_name(obj)
        excerpts = [e.excerpt for e in obj.evidence if e.excerpt]
        tokens = _tokenize(" ".join([name, *excerpts]))

        domain = category = None
        matched: list[str] = []
        for keyword, fields in KEYWORD_RULES.items():
            if keyword in tokens:
                matched.append(keyword)
                domain = fields.get("domain", domain)
                category = fields.get("category", category)

        type_ = None
        name_words = name.strip().lower().split()
        if name_words and name_words[-1] in TYPE_SUFFIX_RULES:
            suffix = name_words[-1]
            matched.append(suffix)
            type_ = TYPE_SUFFIX_RULES[suffix]

        confidence = "Medium" if matched else None

        return ClassificationProposal(
            domain=domain,
            category=category,
            type=type_,
            matched_keywords=matched,
            confidence=confidence,
        )


def apply_classification(obj: OCOMObject, proposal: ClassificationProposal) -> OCOMObject:
    """Returns a new OCOMObject with the proposal applied. An empty
    proposal changes nothing — an engine with nothing to propose adds
    nothing, rather than recording a hollow "classified" action."""
    if proposal.is_empty:
        return obj

    timestamp = datetime.now(timezone.utc)
    evidence_identity = f"evidence:oi-classification:{obj.identity}:{len(obj.evidence)}"
    upstream_reference = obj.evidence[0].identity if obj.evidence else obj.identity

    new_evidence = Evidence(
        identity=evidence_identity,
        source=SOURCE_NAME,
        reference=upstream_reference,
        captured_at=timestamp,
        excerpt=f"Classified based on keyword(s): {', '.join(proposal.matched_keywords)}",
    )

    metadata = dict(obj.metadata)
    attributes = dict(metadata.get("attributes", {}))
    classification_records = list(attributes.get("classification", []))
    classification_records.append(
        {
            "domain": proposal.domain,
            "category": proposal.category,
            "type": proposal.type,
            "evidence": [evidence_identity],
            "confidence": proposal.confidence,
            "timestamp": timestamp.isoformat(),
        }
    )
    attributes["classification"] = classification_records
    metadata["attributes"] = attributes

    classification = list(obj.classification)
    for tag in proposal.flat_tags:
        if tag not in classification:
            classification.append(tag)

    return obj.model_copy(
        update={
            "classification": classification,
            "metadata": metadata,
            "evidence": [*obj.evidence, new_evidence],
        }
    )
