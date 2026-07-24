"""AnswerComposer v0.1 (M009-010).

Uses a hermetic, hand-built RetrievalResult/RepositoryIndex/KnowledgeRegistry
rather than going through RetrievalEngine — Composer's own contract is
"transform this RetrievalResult," so its tests should not depend on
how the result was produced. One real-repository integration test
lives in test_reader_pipeline.py instead, exercising the full chain.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ocom_reader.composer.answer_composer import AnswerComposer
from ocom_reader.composer.formatter import explain_reason, render
from ocom_reader.indexer.models import DocumentIndexEntry, RepositoryIndex
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry import KnowledgeRegistry
from ocom_reader.registry.relations import KnowledgeRelation
from ocom_reader.retrieval.models import MatchReason, QueryObject, RetrievalMatch, RetrievalResult


def _doc(doc_id: str, title: str, document_type: str = "ADR") -> DocumentIndexEntry:
    return DocumentIndexEntry(
        id=doc_id,
        path=doc_id,
        title=title,
        document_type=document_type,
        last_modified=datetime.now(timezone.utc),
    )


def _entry(registry_id: str, entry_type: str = "ADR") -> RegistryEntry:
    return RegistryEntry(registry_id=registry_id, document_id=registry_id, entry_type=entry_type)


def _primary_match(
    registry_id: str, kind: str = "title_match", detail: str = "x", score: float = 10.0, entry_type: str = "ADR"
) -> RetrievalMatch:
    return RetrievalMatch(
        entry=_entry(registry_id, entry_type=entry_type), reasons=[MatchReason(kind=kind, detail=detail)], score=score
    )


def _secondary_match(registry_id: str, source: str, kind: str = "builds_on", score: float = 3.0) -> RetrievalMatch:
    return RetrievalMatch(entry=_entry(registry_id), reasons=[MatchReason(kind=kind, detail=source)], score=score)


def _result(query: str, matches: list[RetrievalMatch]) -> RetrievalResult:
    return RetrievalResult(query=QueryObject(raw=query, tokens=query.lower().split()), matches=matches)


# --- Grouping: evidence vs related --------------------------------------------


def test_primary_matches_become_evidence() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "Doc A")])
    registry = KnowledgeRegistry(entries=[_entry("a.md")], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md")]))

    assert len(answer.evidence) == 1
    assert answer.related_documents == []
    assert answer.evidence[0].document.title == "Doc A"


def test_secondary_matches_become_related_documents() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "Doc A"), _doc("b.md", "Doc B")])
    registry = KnowledgeRegistry(entries=[_entry("a.md"), _entry("b.md")], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md"), _secondary_match("b.md", source="a.md")]))

    assert [d.document.registry_id for d in answer.evidence] == ["a.md"]
    assert [d.document.registry_id for d in answer.related_documents] == ["b.md"]


def test_a_match_with_both_text_and_relation_reasons_is_evidence_not_related() -> None:
    """A document that matched the query text directly is evidence, even
    if it also happens to carry a relation reason (can't currently
    happen from RetrievalEngine's own output, but Composer's own
    classification rule — 'any text reason -> evidence' — must not
    depend on that)."""
    index = RepositoryIndex(entries=[_doc("a.md", "Doc A")])
    registry = KnowledgeRegistry(entries=[_entry("a.md")], relations=[])
    composer = AnswerComposer(index, registry)
    match = RetrievalMatch(
        entry=_entry("a.md"),
        reasons=[MatchReason(kind="title_match", detail="x"), MatchReason(kind="builds_on", detail="b.md")],
        score=13.0,
    )

    answer = composer.compose(_result("q", [match]))

    assert len(answer.evidence) == 1
    assert answer.related_documents == []


# --- Order preservation (no re-ranking) ---------------------------------------


def test_composer_preserves_the_order_retrievalresult_already_provides() -> None:
    """Composer must never re-sort — RetrievalResult.matches order (set
    by Ranker) is authoritative and preserved as-is within each group."""
    index = RepositoryIndex(entries=[_doc("low.md", "Low"), _doc("high.md", "High")])
    registry = KnowledgeRegistry(entries=[_entry("low.md"), _entry("high.md")], relations=[])
    composer = AnswerComposer(index, registry)
    # Deliberately out of score order — composer must not reorder by score.
    matches = [_primary_match("low.md", score=1.0), _primary_match("high.md", score=99.0)]

    answer = composer.compose(_result("q", matches))

    assert [d.document.registry_id for d in answer.evidence] == ["low.md", "high.md"]


# --- Title/path resolution -----------------------------------------------------


def test_title_and_path_are_resolved_from_the_index() -> None:
    index = RepositoryIndex(entries=[_doc("docs/a.md", "A Document", document_type="README")])
    registry = KnowledgeRegistry(entries=[_entry("docs/a.md", entry_type="README")], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("docs/a.md", entry_type="README")]))

    doc = answer.evidence[0].document
    assert doc.title == "A Document"
    assert doc.path == "docs/a.md"
    assert doc.document_type == "README"


# --- Answer text -----------------------------------------------------------


def test_answer_text_for_no_matches() -> None:
    index = RepositoryIndex(entries=[])
    registry = KnowledgeRegistry(entries=[], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("nothing", []))

    assert answer.answer == 'No documentation found for "nothing".'
    assert answer.grounded is False


def test_answer_text_names_the_top_match_and_count() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "Top Doc"), _doc("b.md", "Second Doc")])
    registry = KnowledgeRegistry(entries=[_entry("a.md"), _entry("b.md")], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md", score=10), _primary_match("b.md", score=5)]))

    assert answer.answer == 'Found 2 relevant document(s) for "q". Most relevant: "Top Doc".'
    assert answer.grounded is True


# --- Reading order -----------------------------------------------------------


def test_reading_order_follows_builds_on_base_before_dependent() -> None:
    index = RepositoryIndex(entries=[_doc("base.md", "Base"), _doc("ext.md", "Extension")])
    registry = KnowledgeRegistry(
        entries=[_entry("base.md"), _entry("ext.md")],
        relations=[KnowledgeRelation(source_id="ext.md", target_id="base.md", relation_type="builds_on")],
    )
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("ext.md"), _secondary_match("base.md", source="ext.md")]))

    assert [d.registry_id for d in answer.reading_order] == ["base.md", "ext.md"]


def test_reading_order_follows_architecture_sequence_earlier_before_later() -> None:
    index = RepositoryIndex(entries=[_doc("adr1.md", "ADR 1"), _doc("adr2.md", "ADR 2")])
    registry = KnowledgeRegistry(
        entries=[_entry("adr1.md"), _entry("adr2.md")],
        relations=[KnowledgeRelation(source_id="adr1.md", target_id="adr2.md", relation_type="architecture_sequence")],
    )
    composer = AnswerComposer(index, registry)

    answer = composer.compose(
        _result("q", [_primary_match("adr1.md"), _secondary_match("adr2.md", source="adr1.md", kind="architecture_sequence")])
    )

    assert [d.registry_id for d in answer.reading_order] == ["adr1.md", "adr2.md"]


def test_reading_order_is_empty_when_no_ordering_relations_exist() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "A"), _doc("b.md", "B")])
    registry = KnowledgeRegistry(entries=[_entry("a.md"), _entry("b.md")], relations=[])
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md"), _primary_match("b.md")]))

    assert answer.reading_order == []


def test_references_relation_never_contributes_to_reading_order() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "A"), _doc("b.md", "B")])
    registry = KnowledgeRegistry(
        entries=[_entry("a.md"), _entry("b.md")],
        relations=[KnowledgeRelation(source_id="a.md", target_id="b.md", relation_type="references")],
    )
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md"), _secondary_match("b.md", source="a.md", kind="references")]))

    assert answer.reading_order == []


def test_reading_order_only_considers_documents_already_in_the_result(tmp_path=None) -> None:
    """A builds_on edge to a document NOT in the result set must not
    pull that document into reading_order — Composer only orders what
    Retrieval already surfaced, never adds new documents."""
    index = RepositoryIndex(entries=[_doc("a.md", "A"), _doc("outside.md", "Outside")])
    registry = KnowledgeRegistry(
        entries=[_entry("a.md"), _entry("outside.md")],
        relations=[KnowledgeRelation(source_id="a.md", target_id="outside.md", relation_type="builds_on")],
    )
    composer = AnswerComposer(index, registry)

    answer = composer.compose(_result("q", [_primary_match("a.md")]))

    assert answer.reading_order == []
    assert "outside.md" not in {d.document.registry_id for d in answer.evidence + answer.related_documents}


# --- Dedup (defensive) ---------------------------------------------------------


def test_duplicate_registry_id_in_input_is_merged_not_listed_twice() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "A")])
    registry = KnowledgeRegistry(entries=[_entry("a.md")], relations=[])
    composer = AnswerComposer(index, registry)
    matches = [
        _primary_match("a.md", kind="title_match", detail="x"),
        _primary_match("a.md", kind="heading_match", detail="y"),
    ]

    answer = composer.compose(_result("q", matches))

    assert len(answer.evidence) == 1
    assert len(answer.evidence[0].reasons) == 2


# --- No decision-making invariant ----------------------------------------------


def test_composer_never_drops_a_document_present_in_the_result() -> None:
    """Every distinct registry_id in the input must appear in either
    evidence or related_documents — Composer performs no relevance
    filtering of its own."""
    index = RepositoryIndex(entries=[_doc(f"d{i}.md", f"Doc {i}") for i in range(5)])
    registry = KnowledgeRegistry(entries=[_entry(f"d{i}.md") for i in range(5)], relations=[])
    composer = AnswerComposer(index, registry)
    matches = [_primary_match(f"d{i}.md") for i in range(5)]

    answer = composer.compose(_result("q", matches))

    output_ids = {d.document.registry_id for d in answer.evidence + answer.related_documents}
    assert output_ids == {f"d{i}.md" for i in range(5)}


def test_composer_does_not_mutate_its_inputs() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "A")])
    registry = KnowledgeRegistry(entries=[_entry("a.md")], relations=[])
    result = _result("q", [_primary_match("a.md")])
    index_before = index.model_dump()
    registry_before = registry.model_dump()
    result_before = result.model_dump()

    AnswerComposer(index, registry).compose(result)

    assert index.model_dump() == index_before
    assert registry.model_dump() == registry_before
    assert result.model_dump() == result_before


def test_compose_is_deterministic() -> None:
    index = RepositoryIndex(entries=[_doc("a.md", "A"), _doc("b.md", "B")])
    registry = KnowledgeRegistry(
        entries=[_entry("a.md"), _entry("b.md")],
        relations=[KnowledgeRelation(source_id="b.md", target_id="a.md", relation_type="builds_on")],
    )
    composer = AnswerComposer(index, registry)
    result = _result("q", [_primary_match("a.md"), _secondary_match("b.md", source="a.md")])

    first = composer.compose(result).model_dump()
    second = composer.compose(result).model_dump()

    assert first == second


# --- Formatter -----------------------------------------------------------


def test_explain_reason_uses_the_fixed_template_table() -> None:
    assert explain_reason(MatchReason(kind="title_match", detail="runtime")) == "Title match: runtime"
    assert (
        explain_reason(MatchReason(kind="builds_on", detail="a.md")) == "Related via builds_on to a.md"
    )


def test_explain_reason_falls_back_for_an_unknown_kind() -> None:
    assert explain_reason(MatchReason(kind="mystery", detail="x")) == "mystery: x"


def test_render_always_includes_all_four_sections_in_order() -> None:
    index = RepositoryIndex(entries=[])
    registry = KnowledgeRegistry(entries=[], relations=[])
    answer = AnswerComposer(index, registry).compose(_result("nothing", []))

    text = render(answer)

    for section in ["Answer", "Evidence", "Related Documents", "Recommended Reading Order"]:
        assert section in text
    assert text.index("Answer") < text.index("Evidence") < text.index("Related Documents") < text.index(
        "Recommended Reading Order"
    )


def test_render_marks_empty_sections_explicitly() -> None:
    index = RepositoryIndex(entries=[])
    registry = KnowledgeRegistry(entries=[], relations=[])
    answer = AnswerComposer(index, registry).compose(_result("nothing", []))

    text = render(answer)

    assert "(none)" in text
    assert "(not applicable)" in text
