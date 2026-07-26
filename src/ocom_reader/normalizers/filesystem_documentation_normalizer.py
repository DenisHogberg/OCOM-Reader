"""Normalizer v0.1 for the Filesystem Documentation Adapter — no LLM.

Every field is derived from a MemoryEntry (ADR-007; previously a
transient RawDocument — see `adapters/filesystem_documentation.py`'s
`to_memory_entry()`) by simple, deterministic rules: a stable identity
hashed from the file path, a fixed object_type, technical metadata
copied from the raw record, and one Evidence entry pointing back at the
source file. It does not attempt to read or interpret the document's
content as a business object — that requires an LLM (or an equivalent
extraction step) and is deliberately out of scope until this plain,
LLM-free pipeline has been proven end to end.

This class implements the `Normalizer` interface and nothing more.
Replacing it later with an LLM-based Normalizer (structured output +
JSON Schema validation + confidence scoring) requires no change to
that interface, the Adapter, or the core — only a new class here.

Metadata is written under `metadata["technical"]`, per
docs/architecture/ADR-003-metadata-semantic-boundary.md and
docs/architecture/ADR-004-metadata-namespace-migration.md. This
Normalizer never populates `metadata["identity"]` — it derives no name
or concept from the file, only path-derived facts, so it has nothing
identity-relevant to propose.

Identity hashing reconstructs a `Path` from `raw.source_identifier`
and resolves it (`Path(raw.source_identifier).resolve()`) rather than
hashing the string directly — this reproduces the exact pre-ADR-007
behavior (`raw.path.resolve()`), since `source_identifier` is always
the unresolved `str(path)` (see `to_memory_entry()`). This is a
deliberate, verified-byte-identical migration detail, not an oversight.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.memory import MemoryEntry
from ocom_reader.core.object import OCOMObject
from ocom_reader.interfaces.normalizer import Normalizer

SOURCE_NAME = "filesystem-documentation"
EXCERPT_LENGTH = 200


class FilesystemDocumentationNormalizer(Normalizer):
    def normalize(self, raw: MemoryEntry) -> OCOMObject:
        identity = self._build_identity(raw)
        return OCOMObject(
            identity=identity,
            object_type="Document",
            metadata=self._build_metadata(raw),
            evidence=[self._build_evidence(raw, identity)],
        )

    def _build_identity(self, raw: MemoryEntry) -> str:
        """Hash of the resolved path — stable across runs, independent of content."""
        digest = hashlib.sha256(
            str(Path(raw.source_identifier).resolve()).encode("utf-8")
        ).hexdigest()
        return f"fsdoc:{digest[:16]}"

    def _build_metadata(self, raw: MemoryEntry) -> dict[str, Any]:
        return {
            "technical": {**raw.metadata, "content_length": len(raw.raw_content)},
        }

    def _build_evidence(self, raw: MemoryEntry, identity: str) -> Evidence:
        return Evidence(
            identity=f"evidence:{identity}",
            source=SOURCE_NAME,
            reference=raw.source_identifier,
            captured_at=raw.timestamp,
            excerpt=raw.raw_content[:EXCERPT_LENGTH],
        )
