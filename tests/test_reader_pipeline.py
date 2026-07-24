"""Reader (M009-010) — full pipeline integration and end-to-end tests.

Most scenarios use a small, synthetic repository (tmp_path), so tests
don't depend on this project's own documentation staying a fixed
shape. A dedicated real-repository section (bottom) runs the entire
Repository -> Index -> Registry -> Retrieval -> Composer chain against
the live OCOM Reader repository across many distinct queries, the same
discipline used for every prior milestone's integration test.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.composer.models import ComposedAnswer
from ocom_reader.reader import Reader


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# --- Full pipeline correctness -------------------------------------------------


def test_reader_answers_from_a_synthetic_repository(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nDescribes the runtime.")
    reader = Reader(tmp_path)

    answer = reader.answer("runtime")

    assert isinstance(answer, ComposedAnswer)
    assert answer.grounded is True
    assert answer.evidence[0].document.title == "Runtime"


def test_reader_answer_reflects_relations_end_to_end(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    reader = Reader(tmp_path)

    answer = reader.answer("runtime")

    related_titles = {d.document.title for d in answer.related_documents}
    assert "Foundation" in related_titles
    assert [d.title for d in answer.reading_order] == ["Foundation", "Runtime"]


def test_reader_answer_for_unmatched_query_is_ungrounded(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    reader = Reader(tmp_path)

    answer = reader.answer("nonexistentxyz")

    assert answer.grounded is False
    assert answer.evidence == []
    assert answer.related_documents == []
    assert answer.reading_order == []


def test_reader_search_returns_ranked_matches(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(tmp_path, "docs/architecture/ADR-002-other.md", "# Other\n\nMentions runtime only in passing text here.")
    reader = Reader(tmp_path)

    matches = reader.search("runtime")

    assert [m.entry.registry_id for m in matches][0] == "docs/architecture/ADR-001-runtime.md"


def test_reader_related_returns_direct_neighbors(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    reader = Reader(tmp_path)

    related = reader.related("docs/architecture/ADR-002-runtime.md")

    assert [e.registry_id for e in related] == ["docs/architecture/ADR-001-foundation.md"]


def test_reader_explain_covers_both_evidence_and_related(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    reader = Reader(tmp_path)

    explained = reader.explain("runtime")

    ids = {d.document.registry_id for d in explained}
    assert ids == {"docs/architecture/ADR-001-foundation.md", "docs/architecture/ADR-002-runtime.md"}
    for doc in explained:
        assert doc.reasons


# --- Determinism and statelessness across the whole pipeline -------------------


def test_reader_answer_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    reader = Reader(tmp_path)

    first = reader.answer("runtime").model_dump()
    second = reader.answer("runtime").model_dump()

    assert first == second


def test_reader_calls_do_not_pollute_each_other(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(tmp_path, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\nBody.")
    reader = Reader(tmp_path)

    before = reader.answer("runtime").model_dump()
    reader.answer("evidence")
    reader.search("evidence")
    after = reader.answer("runtime").model_dump()

    assert before == after


# --- Edge cases -----------------------------------------------------------


def test_reader_on_an_empty_repository(tmp_path: Path) -> None:
    reader = Reader(tmp_path)

    answer = reader.answer("anything")

    assert answer.grounded is False
    assert answer.evidence == []


def test_reader_related_of_unknown_id_is_empty(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    reader = Reader(tmp_path)

    assert reader.related("does/not/exist.md") == []


# --- Real repository verification -----------------------------------------


def test_reader_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    reader = Reader(repo_root)

    queries = [
        "identity resolution",
        "runtime",
        "evidence",
        "registry",
        "retrieval",
        "classification",
        "how does runtime work",
        "knowledge registry architecture",
        "repository indexer",
        "answer composer",
        "metadata namespace",
        "zzznonexistenttermxyz",
    ]

    for query in queries:
        answer = reader.answer(query)
        assert isinstance(answer, ComposedAnswer)
        assert (len(answer.evidence) > 0) == answer.grounded

    # Determinism against real data.
    for query in queries[:3]:
        assert reader.answer(query).model_dump() == reader.answer(query).model_dump()

    # A concrete, known-relevant document must be found for a real query.
    identity_answer = reader.answer("identity resolution")
    ids = {d.document.registry_id for d in identity_answer.evidence}
    assert "docs/architecture/MILESTONE-003.md" in ids


def test_reader_real_repository_no_side_effects_across_a_full_session() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    reader = Reader(repo_root)
    index_before = reader._index.model_dump()
    registry_before = reader._registry.model_dump()

    for query in ["runtime", "evidence", "registry"]:
        reader.answer(query)
        reader.search(query)
        reader.explain(query)
    reader.related("docs/architecture/MILESTONE-007.md")

    assert reader._index.model_dump() == index_before
    assert reader._registry.model_dump() == registry_before
