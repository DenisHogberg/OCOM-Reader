"""LLMDocumentNormalizer contract test.

Uses an injected fake LLM client — no network call, no API key, fully
deterministic — the same way the rest of this suite avoids real I/O.
The real Anthropic-backed client (AnthropicLLMClient) is exercised
manually, outside pytest, once ANTHROPIC_API_KEY is configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ocom_reader.adapters.filesystem_documentation import FilesystemDocumentationAdapter
from ocom_reader.core.object import OCOMObject
from ocom_reader.normalizers.llm_document_normalizer import LLMDocumentNormalizer


class FakeLLMClient:
    """Deterministic stand-in for a real LLM call."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def extract(self, content: str) -> dict[str, Any]:
        return self._response


def _fetch_one(tmp_path: Path, name: str, content: str):
    (tmp_path / name).write_text(content)
    [record] = list(FilesystemDocumentationAdapter(tmp_path).fetch())
    return record


def test_normalize_returns_valid_ocom_object(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Object\n\nAn Object is identifiable.")
    client = FakeLLMClient(
        {"concept": "OCOM Object", "object_type": "Document", "excerpt": "An Object is identifiable."}
    )

    obj = LLMDocumentNormalizer(client).normalize(record)

    assert isinstance(obj, OCOMObject)
    assert obj.identity == "concept:ocom-object"
    assert obj.metadata["identity"]["concept"] == "OCOM Object"
    assert obj.metadata["technical"]["confidence"] == "Low"
    assert len(obj.evidence) == 1
    assert obj.evidence[0].reference == str(record.path)
    assert obj.evidence[0].excerpt == "An Object is identifiable."


def test_malformed_llm_output_is_rejected(tmp_path: Path) -> None:
    record = _fetch_one(tmp_path, "a.md", "# Object")
    client = FakeLLMClient({"object_type": "Document"})  # missing required "concept"/"excerpt"

    with pytest.raises(ValidationError):
        LLMDocumentNormalizer(client).normalize(record)
