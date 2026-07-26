"""Reasoning Consistency Test v0.1.

Not a test of LLM reasoning quality — no LLM is involved here. It tests
whether the architecture (OCOMObject, Evidence, the deterministic
Normalizer v0.1) can represent the same real-world object described by
two different sources, and whether it is honest about what it cannot
yet do.

Setup: two documents describing the same OCOM concept, in different
language and wording, run through the existing non-LLM pipeline.

What this proves:

1. The deterministic Normalizer assigns identity from the file path,
   not from content meaning. Two different files describing the same
   real object therefore get two different identities. Recognizing
   that A and B are "the same thing" requires interpreting content —
   that is reasoning, and this Normalizer deliberately does not do it.
   This is the correct, honest boundary of this phase, not a bug.
2. Each OCOMObject keeps its own Evidence, so provenance from each
   source is never lost even before any merging happens.
3. The OCOMObject/Evidence shape does not block building a single
   merged representation once *something* (a future LLM-based
   Normalizer, or a human) decides A and B refer to the same object:
   merging is just combining evidence lists under one identity — a
   plain constructor call, no change to core required.

Deciding "are these the same object" is exactly what the next phase
(LLM-based Normalizer with structured output) must supply.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.adapters.filesystem_documentation import (
    FilesystemDocumentationAdapter,
    to_memory_entry,
)
from ocom_reader.core.object import OCOMObject
from ocom_reader.normalizers.filesystem_documentation_normalizer import (
    FilesystemDocumentationNormalizer,
)

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


def _normalize_all(tmp_path: Path) -> list[OCOMObject]:
    adapter = FilesystemDocumentationAdapter(tmp_path)
    normalizer = FilesystemDocumentationNormalizer()
    return [normalizer.normalize(to_memory_entry(raw)) for raw in adapter.fetch()]


def test_deterministic_normalizer_cannot_recognize_same_object_across_sources(
    tmp_path: Path,
) -> None:
    (tmp_path / "object_en.md").write_text(DOC_A)
    (tmp_path / "object_ru.md").write_text(DOC_B)

    obj_a, obj_b = _normalize_all(tmp_path)

    # Expected today: path-based identity, not content-based — two files
    # describing the same real-world concept still get two identities.
    # This is the exact gap the LLM-based Normalizer phase must close,
    # not a defect in this deterministic version.
    assert obj_a.identity != obj_b.identity


def test_each_object_preserves_its_own_provenance(tmp_path: Path) -> None:
    (tmp_path / "object_en.md").write_text(DOC_A)
    (tmp_path / "object_ru.md").write_text(DOC_B)

    obj_a, obj_b = _normalize_all(tmp_path)

    assert len(obj_a.evidence) == 1
    assert len(obj_b.evidence) == 1
    assert obj_a.evidence[0].reference.endswith("object_en.md")
    assert obj_b.evidence[0].reference.endswith("object_ru.md")
    assert obj_a.evidence[0].excerpt != obj_b.evidence[0].excerpt


def test_architecture_supports_a_merged_representation(tmp_path: Path) -> None:
    (tmp_path / "object_en.md").write_text(DOC_A)
    (tmp_path / "object_ru.md").write_text(DOC_B)

    obj_a, obj_b = _normalize_all(tmp_path)

    # No merging logic exists in the pipeline yet — deciding that A and
    # B are the same object belongs to a future reasoning step. This
    # only proves the OCOMObject shape does not block it: combining
    # evidence from two sources under one identity is a plain
    # constructor call, nothing more.
    merged = OCOMObject(
        identity=f"merged:{obj_a.identity}+{obj_b.identity}",
        object_type=obj_a.object_type,
        evidence=obj_a.evidence + obj_b.evidence,
    )

    assert merged.object_type == "Document"
    assert len(merged.evidence) == 2
    assert {e.reference for e in merged.evidence} == {
        obj_a.evidence[0].reference,
        obj_b.evidence[0].reference,
    }
