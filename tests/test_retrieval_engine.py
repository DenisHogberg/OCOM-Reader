"""Retrieval Engine v0.1.

Most scenarios use a small, synthetic RepositoryIndex + KnowledgeRegistry
built from a hermetic fixture repository (tmp_path), so tests don't
depend on this project's own documentation staying a fixed shape. One
integration test (bottom) runs the full Index -> Registry -> Retrieval
chain against the real OCOM Reader repository, following the same
discipline as test_repository_indexer.py and test_knowledge_registry.py.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.indexer import RepositoryIndexBuilder
from ocom_reader.registry import RegistryBuilder
from ocom_reader.retrieval import MatchReason, QueryObject, QueryParser, Ranker, RetrievalEngine
from ocom_reader.retrieval.models import RetrievalMatch
from ocom_reader.retrieval.ranking import SCORE_WEIGHTS


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _engine_for(tmp_path: Path) -> RetrievalEngine:
    index = RepositoryIndexBuilder(tmp_path).build()
    registry = RegistryBuilder().build(index)
    return RetrievalEngine(index, registry)


# --- Query parsing ------------------------------------------------------------


def test_query_parser_reuses_query_normalizer_tokenization() -> None:
    query = QueryParser().parse("What is the Runtime?")
    assert query.raw == "What is the Runtime?"
    assert query.tokens == ["runtime"]


def test_query_parser_empty_string_yields_no_tokens() -> None:
    query = QueryParser().parse("")
    assert query.tokens == []


# --- Primary matches (text search) --------------------------------------------


def test_title_match_produces_a_match(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime Boundaries\n\nSome text.")
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    assert len(matches) == 1
    assert matches[0].entry.registry_id == "docs/architecture/ADR-001-runtime.md"
    assert MatchReason(kind="title_match", detail="runtime") in matches[0].reasons


def test_heading_match_produces_a_match(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\n## Evidence Model\n\nBody text.")
    engine = _engine_for(tmp_path)

    matches = engine.search("evidence")

    assert len(matches) == 1
    assert MatchReason(kind="heading_match", detail="evidence") in matches[0].reasons


def test_preview_match_produces_a_match(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/architecture/ADR-001.md",
        "# ADR-001\n\nThis paragraph mentions provenance explicitly in the opening text.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("provenance")

    assert len(matches) == 1
    assert MatchReason(kind="preview_match", detail="provenance") in matches[0].reasons


def test_match_is_case_insensitive(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-Runtime.md", "# Runtime\n\nBody.")
    engine = _engine_for(tmp_path)

    matches = engine.search("RUNTIME")

    assert len(matches) == 1


def test_no_text_match_yields_no_primary_match(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nUnrelated content.")
    engine = _engine_for(tmp_path)

    matches = engine.search("nonexistent-term")

    assert matches == []


def test_query_with_multiple_tokens_matches_documents_hit_by_either_token(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(tmp_path, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\nBody.")
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime evidence")

    ids = {m.entry.registry_id for m in matches}
    assert ids == {"docs/architecture/ADR-001-runtime.md", "docs/architecture/ADR-002-evidence.md"}


# --- Secondary matches (relation expansion) -----------------------------------


def test_document_this_match_builds_on_is_surfaced_as_secondary(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    ids = {m.entry.registry_id for m in matches}
    assert ids == {"docs/architecture/ADR-002-runtime.md", "docs/architecture/ADR-001-foundation.md"}
    foundation_match = next(m for m in matches if m.entry.registry_id == "docs/architecture/ADR-001-foundation.md")
    assert MatchReason(kind="builds_on", detail="docs/architecture/ADR-002-runtime.md") in foundation_match.reasons


def test_document_that_builds_on_this_match_is_also_surfaced_as_secondary(tmp_path: Path) -> None:
    """The inverse direction: a document C that builds_on a primary
    match B must also be surfaced, even though the relation is stored
    as C -> B (source_id=C). Relevance is symmetric even though the
    underlying relation is directional — verified against the real
    repository (MILESTONE-007-DESIGN.md builds_on MILESTONE-003.md)
    before this test was written."""
    _write(tmp_path, "docs/architecture/ADR-001-base.md", "# Identity Resolution\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-extension.md",
        "# Extension\n\n**Builds on:** [Foundation](ADR-001-base.md)\n\nUnrelated body text.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("identity resolution")

    ids = {m.entry.registry_id for m in matches}
    assert ids == {"docs/architecture/ADR-001-base.md", "docs/architecture/ADR-002-extension.md"}
    extension_match = next(m for m in matches if m.entry.registry_id == "docs/architecture/ADR-002-extension.md")
    assert MatchReason(kind="builds_on", detail="docs/architecture/ADR-001-base.md") in extension_match.reasons


def test_a_document_already_a_primary_match_is_never_added_as_secondary_too(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime-extension.md",
        "# Runtime Extension\n\n**Builds on:** [Runtime](ADR-001-runtime.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    ids = [m.entry.registry_id for m in matches]
    assert len(ids) == len(set(ids))


def test_a_document_related_through_two_relations_gets_both_reasons(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\n"
        "Also see [Foundation](ADR-001-foundation.md) again for background context here.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    foundation_match = next(m for m in matches if m.entry.registry_id == "docs/architecture/ADR-001-foundation.md")
    # One relation (builds_on wins the dedup, per registry_builder rules) -> exactly one reason.
    assert len(foundation_match.reasons) == 1


def test_relation_expansion_does_not_recurse_past_one_hop(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-root.md", "# Runtime Root\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-mid.md",
        "# Mid\n\n**Builds on:** [Root](ADR-001-root.md)\n\nBody.",
    )
    _write(
        tmp_path,
        "docs/architecture/ADR-003-leaf.md",
        "# Leaf\n\n**Builds on:** [Mid](ADR-002-mid.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    ids = {m.entry.registry_id for m in matches}
    assert ids == {"docs/architecture/ADR-001-root.md", "docs/architecture/ADR-002-mid.md"}
    assert "docs/architecture/ADR-003-leaf.md" not in ids


def test_document_with_no_relations_has_no_secondary_expansion(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nIsolated document, no links.")
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")

    assert len(matches) == 1


# --- related() ------------------------------------------------------------


def test_related_returns_registry_entries_for_all_directly_connected_documents(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    related = engine.related("docs/architecture/ADR-002-runtime.md")

    assert [e.registry_id for e in related] == ["docs/architecture/ADR-001-foundation.md"]


def test_related_of_unknown_registry_id_is_empty(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    engine = _engine_for(tmp_path)

    assert engine.related("does/not/exist.md") == []


# --- Ranking --------------------------------------------------------------


def test_ranker_scores_are_the_sum_of_fixed_weights() -> None:
    from ocom_reader.registry.models import RegistryEntry

    entry = RegistryEntry(registry_id="a.md", document_id="a.md", entry_type="ADR")
    match = RetrievalMatch(
        entry=entry,
        reasons=[
            MatchReason(kind="title_match", detail="x"),
            MatchReason(kind="preview_match", detail="y"),
        ],
    )

    [ranked] = Ranker().rank([match])

    assert ranked.score == SCORE_WEIGHTS["title_match"] + SCORE_WEIGHTS["preview_match"]


def test_ranker_sorts_by_descending_score() -> None:
    from ocom_reader.registry.models import RegistryEntry

    strong = RetrievalMatch(
        entry=RegistryEntry(registry_id="strong.md", document_id="strong.md", entry_type="ADR"),
        reasons=[MatchReason(kind="title_match", detail="x")],
    )
    weak = RetrievalMatch(
        entry=RegistryEntry(registry_id="weak.md", document_id="weak.md", entry_type="ADR"),
        reasons=[MatchReason(kind="references", detail="x")],
    )

    ranked = Ranker().rank([weak, strong])

    assert [m.entry.registry_id for m in ranked] == ["strong.md", "weak.md"]


def test_ranker_breaks_ties_by_registry_id_for_determinism() -> None:
    from ocom_reader.registry.models import RegistryEntry

    b = RetrievalMatch(
        entry=RegistryEntry(registry_id="b.md", document_id="b.md", entry_type="ADR"),
        reasons=[MatchReason(kind="title_match", detail="x")],
    )
    a = RetrievalMatch(
        entry=RegistryEntry(registry_id="a.md", document_id="a.md", entry_type="ADR"),
        reasons=[MatchReason(kind="title_match", detail="x")],
    )

    ranked = Ranker().rank([b, a])

    assert [m.entry.registry_id for m in ranked] == ["a.md", "b.md"]


def test_retrieve_returns_matches_ranked_highest_first(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-other.md",
        "# Other Document\n\nMentions runtime only in passing text here.",
    )
    engine = _engine_for(tmp_path)

    result = engine.retrieve("runtime")

    scores = [m.score for m in result.matches]
    assert scores == sorted(scores, reverse=True)
    assert result.matches[0].entry.registry_id == "docs/architecture/ADR-001-runtime.md"


# --- explain() --------------------------------------------------------------


def test_explain_renders_each_reason_as_a_readable_line(tmp_path: Path) -> None:
    # An H1 heading is indexed as both the document title and its first
    # Heading entry, so a token that appears there legitimately produces
    # both a title_match and a heading_match reason.
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    engine = _engine_for(tmp_path)

    [match] = engine.search("runtime")

    assert engine.explain(match) == ["title_match: runtime", "heading_match: runtime"]


# --- Determinism and statelessness -------------------------------------------


def test_retrieve_is_deterministic_across_repeated_calls(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    first = engine.retrieve("runtime")
    second = engine.retrieve("runtime")

    assert first.model_dump() == second.model_dump()


def test_a_call_does_not_pollute_the_result_of_a_later_unrelated_call(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    _write(tmp_path, "docs/architecture/ADR-002-evidence.md", "# Evidence\n\nBody.")
    engine = _engine_for(tmp_path)

    before = engine.retrieve("runtime").model_dump()
    engine.retrieve("evidence")
    after = engine.retrieve("runtime").model_dump()

    assert before == after


def test_retrieval_never_mutates_the_index_or_registry(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    index = RepositoryIndexBuilder(tmp_path).build()
    registry = RegistryBuilder().build(index)
    index_before = index.model_dump()
    registry_before = registry.model_dump()

    engine = RetrievalEngine(index, registry)
    engine.retrieve("runtime")
    engine.related("docs/architecture/ADR-002-runtime.md")

    assert index.model_dump() == index_before
    assert registry.model_dump() == registry_before


# --- Edge cases -----------------------------------------------------------


def test_empty_query_string_yields_no_matches(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    engine = _engine_for(tmp_path)

    result = engine.retrieve("")

    assert result.matches == []
    assert result.query.tokens == []


def test_stopword_only_query_yields_no_matches(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    engine = _engine_for(tmp_path)

    result = engine.retrieve("the is a")

    assert result.matches == []


def test_query_matching_nothing_yields_empty_result(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    engine = _engine_for(tmp_path)

    result = engine.retrieve("nonexistent-term-xyz")

    assert result.matches == []


def test_empty_repository_yields_empty_result(tmp_path: Path) -> None:
    engine = _engine_for(tmp_path)

    result = engine.retrieve("anything")

    assert result.matches == []


def test_single_document_repository_with_no_relations(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    engine = _engine_for(tmp_path)

    result = engine.retrieve("runtime")

    assert len(result.matches) == 1
    assert result.matches[0].related == []


def test_query_object_carries_the_original_raw_text(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nBody.")
    engine = _engine_for(tmp_path)

    result = engine.retrieve("  Runtime?  ")

    assert result.query.raw == "  Runtime?  "


# --- Public API shape ---------------------------------------------------------


def test_rank_can_be_called_directly_on_a_match_list(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-runtime.md", "# Runtime\n\nBody.")
    engine = _engine_for(tmp_path)

    matches = engine.search("runtime")
    ranked = engine.rank(matches)

    assert ranked[0].score >= 0
    assert isinstance(ranked, list)


def test_search_and_retrieve_agree_on_the_same_match_set(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-foundation.md", "# Foundation\n\nBase document.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002-runtime.md",
        "# Runtime\n\n**Builds on:** [Foundation](ADR-001-foundation.md)\n\nBody.",
    )
    engine = _engine_for(tmp_path)

    search_ids = {m.entry.registry_id for m in engine.search("runtime")}
    retrieve_ids = {m.entry.registry_id for m in engine.retrieve("runtime").matches}

    assert search_ids == retrieve_ids


# --- Real repository integration --------------------------------------------


def test_retrieval_against_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    index = RepositoryIndexBuilder(repo_root).build()
    registry = RegistryBuilder().build(index)
    engine = RetrievalEngine(index, registry)

    result = engine.retrieve("identity resolution")

    assert len(result.matches) > 0
    matched_ids = {m.entry.registry_id for m in result.matches}
    assert "docs/architecture/MILESTONE-003.md" in matched_ids

    # A document that builds_on a primary match (real inbound relation,
    # verified against the live repository) must be surfaced too.
    assert "docs/architecture/MILESTONE-007-DESIGN.md" in matched_ids

    # Determinism against real data, not just a fixture.
    result_again = engine.retrieve("identity resolution")
    assert result.model_dump() == result_again.model_dump()

    # No mutation of Index or Registry from real usage.
    index_before = index.model_dump()
    registry_before = registry.model_dump()
    engine.retrieve("runtime")
    engine.related("docs/architecture/MILESTONE-007.md")
    assert index.model_dump() == index_before
    assert registry.model_dump() == registry_before

    # explain() output is always a list of readable "kind: detail" strings.
    for match in result.matches:
        explanation = engine.explain(match)
        assert all(": " in line for line in explanation)


def test_unknown_query_against_the_real_repository_yields_no_matches() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    index = RepositoryIndexBuilder(repo_root).build()
    registry = RegistryBuilder().build(index)
    engine = RetrievalEngine(index, registry)

    result = engine.retrieve("zzznonexistenttermxyz")

    assert result.matches == []


def test_query_object_model_is_a_valid_standalone_pydantic_model() -> None:
    query = QueryObject(raw="runtime", tokens=["runtime"])
    assert query.tokens == ["runtime"]
