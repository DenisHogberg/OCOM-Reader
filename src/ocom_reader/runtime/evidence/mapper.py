"""EvidencePresentationMapper v0.1 — Evidence -> EvidenceView.

Read-only: never mutates an Evidence instance, never writes to
Storage, never constructs an OCOMObject, no Core change. It only
computes a new, separate, display-only view from data an Evidence
already carries — per
docs/architecture/OCOM-Runtime-v0.2-Resolution-Evidence-Design.md §6.

Mapping is a small, fixed set of rules, not inference: known source
prefixes get a known source_type and reference cleanup; anything else
is classified "external" and left exactly as given — this mapper does
not guess at a source it doesn't recognize.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.core.evidence import Evidence
from ocom_reader.runtime.evidence.models import EvidenceView

FILESYSTEM_SOURCE = "filesystem-documentation"
OBJECT_INTELLIGENCE_PREFIX = "object-intelligence:"


class EvidencePresentationMapper:
    def to_view(self, evidence: Evidence) -> EvidenceView:
        if evidence.source == FILESYSTEM_SOURCE:
            return EvidenceView(
                source_type="filesystem",
                reference=Path(evidence.reference).name,
                excerpt=evidence.excerpt,
                original_id=evidence.identity,
            )

        if evidence.source.startswith(OBJECT_INTELLIGENCE_PREFIX):
            return EvidenceView(
                source_type="object-intelligence",
                reference=evidence.reference,
                excerpt=evidence.excerpt,
                original_id=evidence.identity,
            )

        # Unknown source: classified "external", never guessed at —
        # reference is passed through exactly as given.
        return EvidenceView(
            source_type="external",
            reference=evidence.reference,
            excerpt=evidence.excerpt,
            original_id=evidence.identity,
        )
