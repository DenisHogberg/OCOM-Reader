"""Repository Indexer — deterministic, structural indexing only.

Most scenarios use a small, synthetic, hermetic fixture repository
(tmp_path) rather than this real one, so tests don't depend on this
project's own documentation staying a fixed shape. One integration
test (bottom) runs the indexer against the real OCOM Reader repository
to prove it works on real data, not just synthetic fixtures — the same
discipline used for test_end_to_end_reasoning_path.py.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.indexer import RepositoryIndexBuilder


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_scans_and_indexes_every_markdown_file(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Sample Repo\n\nAn example.")
    _write(tmp_path, "docs/architecture/ADR-001-example.md", "# ADR-001: Example\n\nSome decision.")
    _write(tmp_path, "docs/architecture/MILESTONE-001.md", "# Milestone One\n\nSome result.")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert {entry.path for entry in index.entries} == {
        "README.md",
        "docs/architecture/ADR-001-example.md",
        "docs/architecture/MILESTONE-001.md",
    }


def test_excludes_venv_and_cache_directories(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Sample Repo")
    _write(tmp_path, ".venv/lib/site-packages/somepkg/README.md", "# Not part of this repo")
    _write(tmp_path, "__pycache__/stale.md", "# Should never appear")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert [entry.path for entry in index.entries] == ["README.md"]


def test_document_types_are_classified_by_path(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001-x.md", "# ADR-001")
    _write(tmp_path, "docs/architecture/MILESTONE-001.md", "# Milestone")
    _write(tmp_path, "docs/architecture/OCOM-Something-Design.md", "# Design")
    _write(tmp_path, "docs/architecture/random-notes.md", "# Notes")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert index.get("README.md").document_type == "README"
    assert index.get("docs/architecture/ADR-001-x.md").document_type == "ADR"
    assert index.get("docs/architecture/MILESTONE-001.md").document_type == "Milestone"
    assert index.get("docs/architecture/OCOM-Something-Design.md").document_type == "Architecture"
    assert index.get("docs/architecture/random-notes.md").document_type == "Architecture"  # by folder


def test_headings_title_and_preview_extraction(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/architecture/ADR-001-example.md",
        "# ADR-001: Example Decision\n\n"
        "**Status:** Accepted\n\n"
        "## Context\n\n"
        "Some reasoning text here.\n\n"
        "## Decision\n\n"
        "The actual decision.\n",
    )

    index = RepositoryIndexBuilder(tmp_path).build()
    entry = index.get("docs/architecture/ADR-001-example.md")

    assert entry.title == "ADR-001: Example Decision"
    assert [h.text for h in entry.headings] == [
        "ADR-001: Example Decision",
        "Context",
        "Decision",
    ]
    assert [h.level for h in entry.headings] == [1, 2, 2]
    assert entry.preview == "**Status:** Accepted"


def test_internal_and_inbound_links_are_resolved_and_deduplicated(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational, cited by others.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n"
        "Builds on [ADR-001](ADR-001.md) and cites it again: [see ADR-001](ADR-001.md).\n"
        "Also links to an external page: [external](https://example.com) "
        "and to source code: [core](../../src/core.py).",
    )

    index = RepositoryIndexBuilder(tmp_path).build()
    adr2 = index.get("docs/architecture/ADR-002.md")
    adr1 = index.get("docs/architecture/ADR-001.md")

    # Cited twice in ADR-002's text, but counted once as an internal link.
    assert adr2.internal_links == ["docs/architecture/ADR-001.md"]
    # Every raw link is still preserved, unfiltered, as an outbound
    # reference — including the repeated ADR-001 citation, unlike
    # internal_links which counts distinct targets, not occurrences.
    assert len(adr2.outbound_references) == 4
    # Inbound is computed on the target, from the other document, deduplicated.
    assert adr1.inbound_references == ["docs/architecture/ADR-002.md"]
    # A document with nothing pointing at it has an empty inbound list.
    assert adr2.inbound_references == []


def test_builds_on_links_are_extracted_from_the_builds_on_header_line(tmp_path: Path) -> None:
    """Added for MILESTONE-007's Knowledge Registry: the **Builds on:**
    header line already used consistently across this project's own
    ADRs/Milestones is a distinct signal from a generic body-text link."""
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nFoundational.")
    _write(tmp_path, "docs/architecture/MILESTONE-001.md", "# Milestone 001\n\nSome result.")
    _write(
        tmp_path,
        "docs/architecture/ADR-002.md",
        "# ADR-002\n\n"
        "**Builds on:** [ADR-001](ADR-001.md), [MILESTONE-001](MILESTONE-001.md)\n\n"
        "Elsewhere in the body, a plain reference: see also [ADR-001](ADR-001.md).",
    )

    index = RepositoryIndexBuilder(tmp_path).build()
    adr2 = index.get("docs/architecture/ADR-002.md")

    assert set(adr2.builds_on_links) == {
        "docs/architecture/ADR-001.md",
        "docs/architecture/MILESTONE-001.md",
    }
    # The body-text mention is still a plain internal link, distinct
    # from — and not required to be excluded from — internal_links.
    assert "docs/architecture/ADR-001.md" in adr2.internal_links


def test_no_builds_on_line_produces_an_empty_list(tmp_path: Path) -> None:
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\nNo builds-on line here.")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert index.get("docs/architecture/ADR-001.md").builds_on_links == []


def test_invalid_and_empty_files_are_reported_not_crashed_on(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Real content")
    empty_path = tmp_path / "docs" / "empty.md"
    empty_path.parent.mkdir(parents=True, exist_ok=True)
    empty_path.write_text("   \n\n  ")
    binary_path = tmp_path / "docs" / "not-really-markdown.md"
    binary_path.write_bytes(b"\xff\xfe\x00\x01binary-garbage")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert [entry.path for entry in index.entries] == ["README.md"]
    invalid_paths = {doc.path for doc in index.invalid}
    assert invalid_paths == {"docs/empty.md", "docs/not-really-markdown.md"}


def test_duplicate_content_is_detected_across_different_paths(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "# Same Content\n\nIdentical text.")
    _write(tmp_path, "docs/b.md", "# Same Content\n\nIdentical text.")
    _write(tmp_path, "docs/c.md", "# Different\n\nUnique text.")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert index.duplicates == [["docs/a.md", "docs/b.md"]]


def test_build_is_deterministic_across_repeated_runs(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001.md", "# ADR-001\n\n[README](../../README.md)")

    first = RepositoryIndexBuilder(tmp_path).build()
    second = RepositoryIndexBuilder(tmp_path).build()

    assert [e.model_dump() for e in first.entries] == [e.model_dump() for e in second.entries]
    assert first.duplicates == second.duplicates
    assert [d.model_dump() for d in first.invalid] == [d.model_dump() for d in second.invalid]


def test_index_query_api(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Repo")
    _write(tmp_path, "docs/architecture/ADR-001-x.md", "# ADR-001")
    _write(tmp_path, "docs/architecture/ADR-002-y.md", "# ADR-002")

    index = RepositoryIndexBuilder(tmp_path).build()

    assert len(index.all()) == 3
    assert {e.path for e in index.by_type("ADR")} == {
        "docs/architecture/ADR-001-x.md",
        "docs/architecture/ADR-002-y.md",
    }
    assert index.get("README.md").title == "Repo"
    assert index.get("does/not/exist.md") is None


def test_indexes_the_real_ocom_reader_repository() -> None:
    """Integration proof, not a synthetic fixture: the real repository
    this project has been building, scanned for real."""
    repo_root = Path(__file__).resolve().parent.parent

    index = RepositoryIndexBuilder(repo_root).build()

    paths = {entry.path for entry in index.entries}
    assert "README.md" in paths
    assert "docs/architecture/ADR-001-normalizer-architecture.md" in paths
    assert any(entry.document_type == "ADR" for entry in index.entries)
    assert any(entry.document_type == "Milestone" for entry in index.entries)

    adr1 = index.get("docs/architecture/ADR-001-normalizer-architecture.md")
    assert adr1 is not None
    assert "ADR-001" in adr1.title
    # ADR-001 is foundational and is cited by later documents.
    assert len(adr1.inbound_references) > 0
    # No .venv/__pycache__ noise leaked into the index.
    assert not any(".venv" in entry.path for entry in index.entries)
