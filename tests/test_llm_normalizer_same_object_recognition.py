"""LLM-based Normalizer v0.1 — required first test.

Two documents, object_en.md and object_ru.md, describe the same OCOM
concept in different languages (same content as
test_reasoning_consistency_v0_1.py, where the deterministic Normalizer
was shown to structurally be unable to unify them). This test proves
what an LLM-based Normalizer adds: a single identity for both, with
provenance from both sources preserved.

No real LLM call is made here — FakeConceptRecognizer stands in for one,
so the test stays deterministic, offline, and free, exactly like the
rest of this suite. It still reads each document's own content to build
its excerpt, so the two evidence entries are genuinely distinct; only
the concept-recognition step itself is simulated rather than delegated
to a real model. AnthropicLLMClient (llm_document_normalizer.py) is the
real implementation, usable once ANTHROPIC_API_KEY is set — that is
outside the scope of an automated, no-network test suite.

Merging is done here with a plain get-then-save around the existing
Storage interface — no change to Storage, no new architectural layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ocom_reader.adapters.filesystem_documentation import FilesystemDocumentationAdapter
from ocom_reader.normalizers.llm_document_normalizer import LLMDocumentNormalizer
from ocom_reader.storage.local_storage import LocalJSONStorage

DOC_A = (
    "# Object\n\n"
    "An Object is an identifiable and governable element that exists "
    "within the operational model. It can be described, managed, "
    "related, evaluated, or governed throughout its lifecycle."
)

DOC_B = (
    "# Объект\n\n"
    "OCOM Object — это управляемый элемент, который можно "
    "идентифицировать и которым можно управлять на протяжении всего "
    "его жизненного цикла: описывать, связывать с другими элементами "
    "и оценивать."
)


class FakeConceptRecognizer:
    """Stands in for a real LLM call that recognizes the same concept
    regardless of the language it is described in."""

    def extract(self, content: str) -> dict[str, Any]:
        excerpt = next(line for line in content.splitlines() if line and not line.startswith("#"))
        return {"concept": "OCOM Object", "object_type": "Document", "excerpt": excerpt}


def test_two_documents_in_different_languages_resolve_to_one_object(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "object_en.md").write_text(DOC_A)
    (docs_dir / "object_ru.md").write_text(DOC_B)

    adapter = FilesystemDocumentationAdapter(docs_dir)
    normalizer = LLMDocumentNormalizer(FakeConceptRecognizer())
    storage = LocalJSONStorage(tmp_path / "data")

    for raw in adapter.fetch():
        obj = normalizer.normalize(raw)
        existing = storage.get(obj.identity)
        if existing is not None:
            obj = existing.model_copy(update={"evidence": existing.evidence + obj.evidence})
        storage.save(obj)

    # Success criteria: one identity, evidence from both sources, each
    # fragment's provenance preserved.
    stored_objects = list(storage.list())
    assert len(stored_objects) == 1

    [stored] = stored_objects
    assert stored.identity == "concept:ocom-object"
    assert len(stored.evidence) == 2

    references = {e.reference for e in stored.evidence}
    assert references == {
        str(docs_dir / "object_en.md"),
        str(docs_dir / "object_ru.md"),
    }

    excerpts = {e.excerpt for e in stored.evidence}
    assert len(excerpts) == 2  # each source's own supporting fragment survives distinctly
