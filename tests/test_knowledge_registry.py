"""Knowledge Registry v0.1.

Most scenarios use a small, synthetic RepositoryIndex built from a
hermetic fixture repository (tmp_path), so tests don't depend on this
project's own documentation staying a fixed shape. One integration
test (bottom) runs the full Index -> Registry chain against the real
OCOM Reader repository — the same discipline already used for
test_repository_indexer.py and test_end_to_end_reasoning_path.py.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.indexer import RepositoryIndexBuilder
from ocom_reader.registry import KnowledgeRegistry, RegistryBuilder, RegistryEntry
from ocom_reader.registry.relations import KnowledgeRelation


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _registry_for(tmp_path: Path):
    index = RepositoryIndexBuilder(tmp_path).build()
    registry = RegistryBuilder().build(index)
    return index, registry


# --- Build correctness ------------------------------------------------------


def test_one_registry_entry_per_indexed_document(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001-x.md", "# ADR-001")
    _write(tmp_path, "docs/architecture/MILESTONE-001.md", "# Milestone One")

    index, registry = _registry_for(tmp_path)

    assert len(registry.entries) == len(index.entries) == 3
    assert {e.registry_id for e in registry.entries} == {e.id for e in index.entries}


def test_entry_type_mirrors_document_type(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001-x.md", "# ADR-001")

    _, registry = _registry_for(tmp_path)

    assert registry.lookup("README.md").entry_type == "README"
    assert registry.lookup("docs/architecture/ADR-001-x.md").entry_type == "ADR"


# --- Relation correctness ---------------------------------------------------


def test_builds_on_relation_is_derived_from_the_header_line(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)\n\nDecision text.",
    )

    _, registry = _registry_for(tmp_path)

    relation = KnowledgeRelation(
        source_id="docs/architecture/ADR-002.md",
        target_id="docs/architecture/ADR-001.md",
        relation_type="builds_on",
    )
    assert relation in registry.relations


def test_plain_body_link_becomes_references_not_builds_on(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\nSee also [ADR-001](ADR-001.md) for background.",
    )

    _, registry = _registry_for(tmp_path)

    relation_types = {
        r.relation_type
        for r in registry.relations
        if r.source_id == "docs/architecture/ADR-002.md" and r.target_id == "docs/architecture/ADR-001.md"
    }
    assert relation_types == {"references"}


def test_a_link_is_never_double_labeled(tmp_path: Path) -> None:
    """A link that appears both in the **Builds on:** line and again in
    the body must produce exactly one relation for that pair, not two
    competing labels."""
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n"
        "**Builds on:** [ADR-001](ADR-001.md)\n\n"
        "As mentioned, [ADR-001](ADR-001.md) already established this.",
    )

    _, registry = _registry_for(tmp_path)

    pairs = [
        r
        for r in registry.relations
        if r.source_id == "docs/architecture/ADR-002.md" and r.target_id == "docs/architecture/ADR-001.md"
    ]
    assert len(pairs) == 1
    assert pairs[0].relation_type == "builds_on"


def test_architecture_sequence_links_consecutive_numbered_documents(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001-a.md", "# ADR-001")
    _write(tmp_path, "docs/architecture/ADR-002-b.md", "# ADR-002")
    _write(tmp_path, "docs/architecture/ADR-003-c.md", "# ADR-003")
    _write(tmp_path, "docs/architecture/MILESTONE-001.md", "# Milestone 1")
    _write(tmp_path, "docs/architecture/MILESTONE-002.md", "# Milestone 2")

    _, registry = _registry_for(tmp_path)

    sequence = {(r.source_id, r.target_id) for r in registry.relations if r.relation_type == "architecture_sequence"}
    assert sequence == {
        ("docs/architecture/ADR-001-a.md", "docs/architecture/ADR-002-b.md"),
        ("docs/architecture/ADR-002-b.md", "docs/architecture/ADR-003-c.md"),
        ("docs/architecture/MILESTONE-001.md", "docs/architecture/MILESTONE-002.md"),
    }
    # ADRs and Milestones are separate series — no cross-series edge.
    assert ("docs/architecture/ADR-003-c.md", "docs/architecture/MILESTONE-001.md") not in sequence


def test_a_non_existent_link_target_produces_no_relation(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/architecture/ADR-001.md",
        "# ADR-001\n\n**Builds on:** [Nothing](does-not-exist.md)",
    )

    _, registry = _registry_for(tmp_path)

    assert registry.relations == []


# --- Determinism and no duplication -----------------------------------------


def test_registry_build_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)",
    )

    index = RepositoryIndexBuilder(tmp_path).build()
    first = RegistryBuilder().build(index)
    second = RegistryBuilder().build(index)

    assert first.model_dump() == second.model_dump()


def test_no_duplicate_entries_for_the_same_document(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001")

    _, registry = _registry_for(tmp_path)

    ids = [e.registry_id for e in registry.entries]
    assert len(ids) == len(set(ids))


# --- Invariants --------------------------------------------------------------


def test_registry_entry_has_no_content_bearing_field() -> None:
    """Pointer, not copy: the model itself must be structurally
    incapable of holding a title, heading, or document text."""
    assert set(RegistryEntry.model_fields.keys()) == {"registry_id", "document_id", "entry_type"}


def test_registry_never_mutates_the_repository_index(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)",
    )

    index = RepositoryIndexBuilder(tmp_path).build()
    before = index.model_dump()

    RegistryBuilder().build(index)

    assert index.model_dump() == before


def test_every_registry_entry_points_to_an_existing_index_entry(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001")

    index, registry = _registry_for(tmp_path)

    index_ids = {e.id for e in index.entries}
    for entry in registry.entries:
        assert entry.document_id in index_ids


def test_no_self_referential_relations(tmp_path: Path) -> None:
    """A document linking to itself (e.g. an anchor-style self mention)
    must never produce a relation whose source and target are the same
    entry — the closest meaningful reading of "no cyclic references"
    for a lookup-only registry with no general cycle-detection."""
    _write(
        tmp_path,
        "docs/architecture/ADR-001.md",
        "# ADR-001\n\n**Builds on:** [itself](ADR-001.md)\n\nAlso see [itself](ADR-001.md) again.",
    )

    _, registry = _registry_for(tmp_path)

    assert all(r.source_id != r.target_id for r in registry.relations)


def test_registry_is_reproducible_across_independent_index_builds(tmp_path: Path) -> None:
    """Not just the same RepositoryIndex object reused twice (already
    covered above) — two independently-built indexes of the same
    unchanged files must also produce the same Registry."""
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)",
    )

    first = RegistryBuilder().build(RepositoryIndexBuilder(tmp_path).build())
    second = RegistryBuilder().build(RepositoryIndexBuilder(tmp_path).build())

    assert first.model_dump() == second.model_dump()


# --- Public API ---------------------------------------------------------------


def test_lookup_and_get_are_equivalent(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001")

    _, registry = _registry_for(tmp_path)

    assert registry.lookup("docs/architecture/ADR-001.md") == registry.get("docs/architecture/ADR-001.md")


def test_lookup_of_unknown_id_returns_none(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001")

    _, registry = _registry_for(tmp_path)

    assert registry.lookup("does/not/exist.md") is None


def test_contains(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001")

    _, registry = _registry_for(tmp_path)

    assert registry.contains("docs/architecture/ADR-001.md") is True
    assert registry.contains("nope.md") is False


def test_neighbors_includes_both_directions(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)",
    )

    _, registry = _registry_for(tmp_path)

    assert [e.registry_id for e in registry.neighbors("docs/architecture/ADR-001.md")] == [
        "docs/architecture/ADR-002.md"
    ]
    assert [e.registry_id for e in registry.neighbors("docs/architecture/ADR-002.md")] == [
        "docs/architecture/ADR-001.md"
    ]


def test_related_filters_by_relation_type(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n**Builds on:** [ADR-001](ADR-001.md)",
    )

    _, registry = _registry_for(tmp_path)

    assert [e.registry_id for e in registry.related("docs/architecture/ADR-002.md", "builds_on")] == [
        "docs/architecture/ADR-001.md"
    ]
    assert registry.related("docs/architecture/ADR-002.md", "references") == []


# --- Edge cases -----------------------------------------------------------


def test_empty_repository_produces_an_empty_registry(tmp_path: Path) -> None:
    _, registry = _registry_for(tmp_path)

    assert registry.entries == []
    assert registry.relations == []


def test_document_with_no_links_has_no_outgoing_relations(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nNo links at all.")

    _, registry = _registry_for(tmp_path)

    assert registry.relations == []
    assert registry.entries[0].registry_id == "docs/architecture/ADR-001.md"


def test_isolated_registry_is_a_valid_pydantic_model() -> None:
    """The container itself must be constructible with no builder at
    all — proving KnowledgeRegistry has no hidden dependency on
    RegistryBuilder or RepositoryIndex to exist."""
    registry = KnowledgeRegistry(
        entries=[RegistryEntry(registry_id="a", document_id="a.md", entry_type="ADR")],
        relations=[],
    )
    assert registry.lookup("a") is not None


# --- Real repository integration --------------------------------------------


def test_builds_a_registry_from_the_real_ocom_reader_repository() -> None:
    repo_root = Path(__file__).resolve().parent.parent

    index = RepositoryIndexBuilder(repo_root).build()
    registry = RegistryBuilder().build(index)

    assert len(registry.entries) == len(index.entries)
    assert len(registry.entries) > 0

    adr3 = registry.lookup("docs/architecture/ADR-003-metadata-semantic-boundary.md")
    assert adr3 is not None
    builds_on = {e.registry_id for e in registry.related(adr3.registry_id, "builds_on")}
    assert "docs/architecture/MILESTONE-003.md" in builds_on

    # No self-referential relation anywhere in the real data either.
    assert all(r.source_id != r.target_id for r in registry.relations)

    # Determinism against the real repository, not just a fixture.
    registry_again = RegistryBuilder().build(index)
    assert registry.model_dump() == registry_again.model_dump()
