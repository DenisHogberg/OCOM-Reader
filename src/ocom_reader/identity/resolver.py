"""IdentityResolver v0.1 — rule-based similarity, stdlib only.

Experimental implementation of Option B from
docs/architecture/OCOM-Identity-Resolution-v0.1.md §3. Standalone: not
called from agent/ or anywhere else. Given two OCOMObjects, decides
MATCH / NEW / UNCERTAIN using only fields OCOM Reader already
produces — object_type, classification, metadata["identity"], and
evidence presence. No LLM, no embeddings, no new dependency.

Metadata access follows docs/architecture/ADR-003-metadata-semantic-boundary.md
and docs/architecture/ADR-004-metadata-namespace-migration.md: only the
`identity` namespace is read. `metadata["technical"]` and
`metadata["attributes"]` are ignored entirely — this is the concrete
fix for the contamination MILESTONE-003 found, where a free-text value
scored the same way as a name produced a false MATCH. An object with no
`identity` namespace populated contributes no metadata signal at all
(treated as an empty set, not an error).

Scoring: word-overlap (Jaccard) over normalized metadata["identity"]
values, combined with word-overlap over classification tags. Metadata
carries more weight (0.6) than classification (0.4) because it is the
more specific signal, but classification is what actually distinguishes
a same-shaped-but-unrelated pair (e.g. "OCOM Object" / "Payment Object")
from a same-shaped, plausibly-related pair (e.g. "Affiliate Manager" /
"Partner Manager") — metadata-name similarity alone cannot tell these
apart (see MILESTONE-003 for this experiment's write-up).
"""

from __future__ import annotations

import re
from typing import Any

from ocom_reader.core.object import OCOMObject
from ocom_reader.identity.decision import IdentityDecision

MATCH_THRESHOLD = 0.9
UNCERTAIN_THRESHOLD = 0.5

METADATA_WEIGHT = 0.6
CLASSIFICATION_WEIGHT = 0.4


def _tokenize(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _flatten_identity_values(identity_namespace: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in identity_namespace.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return values


def _metadata_tokens(obj: OCOMObject) -> set[str]:
    identity_namespace = obj.metadata.get("identity")
    if not isinstance(identity_namespace, dict):
        return set()
    return _tokenize(" ".join(_flatten_identity_values(identity_namespace)))


def _classification_tokens(obj: OCOMObject) -> set[str]:
    return {c.lower() for c in obj.classification}


class IdentityResolver:
    def resolve(self, candidate: OCOMObject, existing: OCOMObject) -> IdentityDecision:
        if candidate.object_type != existing.object_type:
            return IdentityDecision(
                result="NEW",
                confidence="Verified",
                reasoning=(
                    f"object_type mismatch ({candidate.object_type!r} vs "
                    f"{existing.object_type!r}) — different kinds of thing, "
                    "not compared further."
                ),
            )

        metadata_sim = _jaccard(_metadata_tokens(candidate), _metadata_tokens(existing))
        classification_sim = _jaccard(
            _classification_tokens(candidate), _classification_tokens(existing)
        )
        score = METADATA_WEIGHT * metadata_sim + CLASSIFICATION_WEIGHT * classification_sim

        basis = (
            f"metadata_sim={metadata_sim:.2f}, classification_sim={classification_sim:.2f}, "
            f"combined_score={score:.2f}"
        )

        if score >= MATCH_THRESHOLD:
            if not candidate.evidence or not existing.evidence:
                return IdentityDecision(
                    result="UNCERTAIN",
                    confidence="Low",
                    reasoning=(
                        f"{basis} would support MATCH, but at least one side has "
                        "no Evidence — a MATCH cannot be grounded without it "
                        "(Confidence Model: confidence shall not exist without "
                        "supporting evidence)."
                    ),
                )
            return IdentityDecision(
                result="MATCH",
                confidence="High",
                reasoning=f"{basis} >= {MATCH_THRESHOLD} threshold, evidence present on both sides.",
                matched_object_id=existing.identity,
            )

        if score >= UNCERTAIN_THRESHOLD:
            return IdentityDecision(
                result="UNCERTAIN",
                confidence="Low",
                reasoning=f"{basis} is between {UNCERTAIN_THRESHOLD} and {MATCH_THRESHOLD} — plausible but not confident.",
            )

        return IdentityDecision(
            result="NEW",
            confidence="Verified",
            reasoning=f"{basis} < {UNCERTAIN_THRESHOLD} — no meaningful overlap.",
        )
