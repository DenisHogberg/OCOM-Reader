"""RepositoryIndexBuilder — orchestrates Scanner -> Loader -> MarkdownParser
-> MetadataExtractor for every discovered file, then resolves the
cross-document relationships no single-document component can compute
alone: internal link resolution, inbound references, and duplicate
detection by content hash.

Every step is a deterministic, mechanical rule — no ranking, no LLM,
no embeddings, no semantic interpretation (this milestone's own
non-goals). Given the same repository state, this produces the exact
same index every time.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ocom_reader.indexer.loader import DocumentLoader, DocumentLoadError
from ocom_reader.indexer.markdown_parser import MarkdownParser
from ocom_reader.indexer.metadata_extractor import MetadataExtractor
from ocom_reader.indexer.models import DocumentIndexEntry, InvalidDocument, RepositoryIndex
from ocom_reader.indexer.scanner import RepositoryScanner

EXTERNAL_LINK_PREFIXES = ("http://", "https://", "mailto:")


class RepositoryIndexBuilder:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._scanner = RepositoryScanner(self._root)
        self._loader = DocumentLoader()
        self._parser = MarkdownParser()
        self._metadata = MetadataExtractor()

    def build(self) -> RepositoryIndex:
        discovered_paths = self._scanner.scan()
        known_ids = {path.relative_to(self._root).as_posix() for path in discovered_paths}

        entries: list[DocumentIndexEntry] = []
        invalid: list[InvalidDocument] = []

        for path in discovered_paths:
            relative_path = path.relative_to(self._root)

            try:
                loaded = self._loader.load(path)
            except DocumentLoadError as exc:
                invalid.append(InvalidDocument(path=relative_path.as_posix(), reason=str(exc)))
                continue

            if not loaded.content.strip():
                invalid.append(InvalidDocument(path=relative_path.as_posix(), reason="empty file"))
                continue

            parsed = self._parser.parse(loaded.content, fallback_title=relative_path.stem)
            internal_links = self._resolve_internal_links(path, parsed.links, known_ids)
            builds_on_links = self._resolve_internal_links(path, parsed.builds_on_links, known_ids)

            entries.append(
                DocumentIndexEntry(
                    id=self._metadata.document_id(relative_path),
                    path=relative_path.as_posix(),
                    title=parsed.title,
                    document_type=self._metadata.document_type(relative_path),
                    last_modified=loaded.last_modified,
                    headings=parsed.headings,
                    internal_links=internal_links,
                    builds_on_links=builds_on_links,
                    outbound_references=parsed.links,
                    preview=parsed.preview,
                    content_hash=self._metadata.content_hash(loaded.content),
                )
            )

        self._populate_inbound_references(entries)
        duplicates = self._find_duplicates(entries)

        return RepositoryIndex(entries=entries, invalid=invalid, duplicates=duplicates)

    def _resolve_internal_links(self, source_path: Path, links: list[str], known_ids: set) -> list[str]:
        # Distinct target documents, not link occurrences — citing the
        # same document twice in one file is one internal link, not two.
        resolved: dict[str, None] = {}
        for link in links:
            target = link.split("#", 1)[0].strip()
            if not target or target.startswith(EXTERNAL_LINK_PREFIXES):
                continue
            candidate = (source_path.parent / target).resolve()
            try:
                candidate_id = candidate.relative_to(self._root).as_posix()
            except ValueError:
                continue  # points outside the scanned root
            if candidate_id in known_ids:
                resolved[candidate_id] = None
        return list(resolved)

    def _populate_inbound_references(self, entries: list[DocumentIndexEntry]) -> None:
        # A source document may link to the same target more than once
        # (e.g. citing the same ADR twice in one file) — inbound
        # references count distinct linking documents, not link
        # occurrences, so a set per target rather than a raw list.
        inbound: dict[str, set] = defaultdict(set)
        for entry in entries:
            for target_id in set(entry.internal_links):
                inbound[target_id].add(entry.id)
        for entry in entries:
            entry.inbound_references = sorted(inbound.get(entry.id, set()))

    def _find_duplicates(self, entries: list[DocumentIndexEntry]) -> list[list[str]]:
        by_hash: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            by_hash[entry.content_hash].append(entry.id)
        return [sorted(ids) for ids in by_hash.values() if len(ids) > 1]
