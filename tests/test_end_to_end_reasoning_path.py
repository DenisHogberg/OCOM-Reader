"""OCOM End-to-End Reasoning Path v0.1.

Document -> Adapter -> Normalizer -> OCOMObject -> ClassificationEngine
-> IdentityResolver -> Storage -> Agent Query -> Evidence-backed Answer.

Every step is an existing, independently-tested component
(`runtime/pipeline.py` only coordinates them — see its own docstring).
No embeddings, no vector search, no new LLM calls: the LLM boundary is
the same injected-fake-client pattern already used everywhere else in
this suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ocom_reader.adapters.filesystem_documentation import (
    FilesystemDocumentationAdapter,
    to_memory_entry,
)
from ocom_reader.normalizers.llm_document_normalizer import LLMDocumentNormalizer
from ocom_reader.runtime.context import RuntimeContext
from ocom_reader.runtime.pipeline import ask, ingest_document
from ocom_reader.storage.local_storage import LocalJSONStorage


class FakeConceptClient:
    """Deterministic stand-in for a real LLM call — no network, no API key."""

    def __init__(self, concept: str, object_type: str = "Role") -> None:
        self._concept = concept
        self._object_type = object_type

    def extract(self, content: str) -> dict[str, Any]:
        excerpt = next(line for line in content.splitlines() if line and not line.startswith("#"))
        return {"concept": self._concept, "object_type": self._object_type, "excerpt": excerpt}


def _write(docs_dir: Path, filename: str, title: str, body: str) -> None:
    (docs_dir / filename).write_text(f"# {title}\n\n{body}")


def test_full_happy_path_document_to_grounded_answer(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write(
        docs_dir, "AffiliateManager.md", "Affiliate Manager",
        "manages affiliate relationships and commission payouts",
    )

    adapter = FilesystemDocumentationAdapter(docs_dir)
    [raw] = list(adapter.fetch())
    normalizer = LLMDocumentNormalizer(FakeConceptClient("Affiliate Manager"))

    ctx = RuntimeContext.build(LocalJSONStorage(tmp_path / "data"))

    result = ingest_document(to_memory_entry(raw), normalizer, ctx)

    # Classification ran and enriched the object; identity resolution
    # correctly found nothing to compare against yet.
    assert result.decision.result == "NEW"
    assert set(result.stored.classification) == {"Role", "Marketing", "Partner Management"}
    assert len(result.stored.evidence) == 2  # original ingestion evidence + classification evidence

    answer = ask("What is an Affiliate Manager?", ctx)

    assert answer.grounded is True
    assert str(docs_dir / "AffiliateManager.md") in answer.sources
    assert "manages affiliate relationships and commission payouts" in answer.text


def test_unknown_object_is_not_grounded(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write(
        docs_dir, "AffiliateManager.md", "Affiliate Manager",
        "manages affiliate relationships and commission payouts",
    )

    adapter = FilesystemDocumentationAdapter(docs_dir)
    [raw] = list(adapter.fetch())
    ctx = RuntimeContext.build(LocalJSONStorage(tmp_path / "data"))
    ingest_document(to_memory_entry(raw), LLMDocumentNormalizer(FakeConceptClient("Affiliate Manager")), ctx)

    # A query about something never ingested, with no vocabulary overlap
    # with anything in storage.
    answer = ask("Describe wallet reconciliation workflow", ctx)

    assert answer.grounded is False
    assert answer.sources == []
    assert answer.text == "No evidence found to answer this question."


def test_identity_conflict_produces_uncertain_and_does_not_auto_merge(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write(
        docs_dir, "AffiliateManager.md", "Affiliate Manager",
        "manages affiliate relationships and commission payouts",
    )
    _write(
        docs_dir, "AffiliateManagerEU.md", "Affiliate Manager EU",
        "manages affiliate relationships for the EU region",
    )

    adapter = FilesystemDocumentationAdapter(docs_dir)
    raws = {raw.path.name: to_memory_entry(raw) for raw in adapter.fetch()}
    ctx = RuntimeContext.build(LocalJSONStorage(tmp_path / "data"))

    first = ingest_document(
        raws["AffiliateManager.md"], LLMDocumentNormalizer(FakeConceptClient("Affiliate Manager")), ctx
    )
    second = ingest_document(
        raws["AffiliateManagerEU.md"], LLMDocumentNormalizer(FakeConceptClient("Affiliate Manager EU")), ctx
    )

    assert first.decision.result == "NEW"
    assert second.decision.result == "UNCERTAIN"
    assert second.decision.matched_object_id is None

    # No automatic merge: both objects exist separately in Storage.
    stored = list(ctx.storage.list())
    assert len(stored) == 2
    assert first.stored.identity != second.stored.identity
