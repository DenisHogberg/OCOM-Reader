"""Normalizer v0.1 — LLM-based, structured output.

Same contract as FilesystemDocumentationNormalizer: implements
`Normalizer.normalize(raw: MemoryEntry) -> OCOMObject`. Nothing about
OCOMObject, Evidence, Adapter, or Storage changes to support this —
only a new Normalizer is added, exactly as the interface was designed
to allow.

What's different from the deterministic v0.1: identity is derived from
the *concept* the LLM says the document describes, not from the file
path. That is the one thing a non-LLM Normalizer structurally cannot
do (see test_reasoning_consistency_v0_1.py) — recognizing that two
differently worded documents describe the same real-world object
requires interpreting content.

Structured output boundary: the LLM client returns a raw dict, which
is validated against `ExtractionResult` (a pydantic model) before
anything is built from it. A model that returns malformed output fails
validation loudly rather than silently producing a bad OCOMObject.

Confidence: prepared as `metadata["technical"]["confidence"]`, fixed at
`"Low"` per the OCOM Confidence Model (Memory/Confidence.md.docx) —
"AI inference only" is the textbook Low case. No scoring logic is
implemented; this is a placeholder for the future Confidence Model,
not a computed score.

Metadata namespaces follow
docs/architecture/ADR-003-metadata-semantic-boundary.md and
docs/architecture/ADR-004-metadata-namespace-migration.md: the LLM's
extracted `concept` — the one value this Normalizer proposes that is
actually appropriate for identity comparison — goes under
`metadata["identity"]`. Everything else (file facts, confidence) goes
under `metadata["technical"]`.

The LLM call itself is injected (`llm_client`), not hardcoded, so this
class can be tested deterministically without network access or an API
key — see AnthropicLLMClient for the real implementation used outside
tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.memory import MemoryEntry
from ocom_reader.core.object import OCOMObject
from ocom_reader.interfaces.normalizer import Normalizer

SOURCE_NAME = "filesystem-documentation"

EXTRACTION_PROMPT = """You are identifying which real-world concept a document \
describes, regardless of the language it is written in.

Read the document below and respond with ONLY a JSON object, no other text:
{{"concept": "<canonical English name of the concept, e.g. 'OCOM Object'>", \
"object_type": "<one or two words classifying it, e.g. 'Document'>", \
"excerpt": "<a short quote from the document that supports this identification>"}}

Document:
---
{content}
---"""


class ExtractionResult(BaseModel):
    """Validated shape of the LLM's structured output."""

    concept: str
    object_type: str = "Document"
    excerpt: str


class LLMClient(Protocol):
    """Anything that can turn document content into a raw extraction dict."""

    def extract(self, content: str) -> dict[str, Any]: ...


class AnthropicLLMClient:
    """Real LLMClient backed by the Anthropic API.

    Lazily imports `anthropic` and reads `ANTHROPIC_API_KEY` from the
    environment at call time, not at import time, so this module stays
    importable (and this Normalizer stays testable) without either
    installed or configured.
    """

    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self._model = model

    def extract(self, content: str) -> dict[str, Any]:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(content=content)}
            ],
        )
        return json.loads(message.content[0].text)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "unknown"


def _file_hash(raw: MemoryEntry) -> str:
    """Reconstructs and resolves the Path from `source_identifier`, reproducing
    the exact pre-ADR-007 behavior (`raw.path.resolve()`) byte-identically —
    see `FilesystemDocumentationNormalizer._build_identity` for the same
    pattern with its rationale spelled out."""
    return hashlib.sha256(
        str(Path(raw.source_identifier).resolve()).encode("utf-8")
    ).hexdigest()[:16]


class LLMDocumentNormalizer(Normalizer):
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def normalize(self, raw: MemoryEntry) -> OCOMObject:
        result = ExtractionResult.model_validate(self._llm_client.extract(raw.raw_content))
        identity = f"concept:{_slugify(result.concept)}"

        evidence = Evidence(
            identity=f"evidence:fsdoc:{_file_hash(raw)}",
            source=SOURCE_NAME,
            reference=raw.source_identifier,
            captured_at=raw.timestamp,
            excerpt=result.excerpt,
        )

        return OCOMObject(
            identity=identity,
            object_type=result.object_type,
            metadata={
                "identity": {"concept": result.concept},
                "technical": {
                    **raw.metadata,
                    "content_length": len(raw.raw_content),
                    "confidence": "Low",
                },
            },
            evidence=[evidence],
        )
