"""Filesystem Documentation Adapter.

Reads a local folder of documentation files. Returns raw data only —
content, file path, timestamp, basic metadata. Nothing here knows what
an OCOMObject is, extracts entities, calls an LLM, or normalizes
anything. That boundary belongs entirely to the Normalizer.

`to_memory_entry()` below promotes a `RawDocument` to a persisted
`MemoryEntry`, per ADR-007. It is source-specific glue code (the
mapping from this source's raw shape to Memory Entry's fields), so it
lives here rather than in `core/memory.py` — `core/` must not depend on
`adapters/`. `RawDocument` and `FilesystemDocumentationAdapter` are
unchanged by this: `fetch()` still yields `RawDocument`, exactly as
before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from ocom_reader.core.evidence import Evidence
from ocom_reader.core.memory import MemoryEntry, content_hash
from ocom_reader.interfaces.adapter import Adapter

DEFAULT_EXTENSIONS: Sequence[str] = (".md", ".txt")
SOURCE_NAME = "filesystem-documentation"
EXCERPT_LENGTH = 200


@dataclass
class RawDocument:
    """Raw, source-shaped record. Not an OCOMObject."""

    path: Path
    content: str
    modified_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class FilesystemDocumentationAdapter(Adapter):
    def __init__(
        self,
        root_dir: Path,
        extensions: Sequence[str] = DEFAULT_EXTENSIONS,
    ) -> None:
        self._root_dir = root_dir
        self._extensions = tuple(ext.lower() for ext in extensions)

    def fetch(self) -> Iterator[RawDocument]:
        for path in sorted(self._root_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self._extensions:
                continue

            stat = path.stat()
            yield RawDocument(
                path=path,
                content=path.read_text(encoding="utf-8", errors="replace"),
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                metadata={
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size,
                },
            )


def to_memory_entry(raw: RawDocument, source: str = SOURCE_NAME) -> MemoryEntry:
    """Promote a RawDocument to a persisted MemoryEntry. See ADR-007.

    `source_identifier` is deliberately `str(raw.path)` — unresolved,
    exactly what Normalizers historically embedded in `Evidence.reference`
    — not `raw.path.resolve()`. Preserving the unresolved form here keeps
    both existing behaviors (evidence reference *and*, via
    `Path(entry.source_identifier).resolve()` downstream, resolved-path
    identity hashing) byte-identical to before this migration.
    """
    entry_id = content_hash(raw.content)
    return MemoryEntry(
        id=entry_id,
        source=source,
        source_identifier=str(raw.path),
        timestamp=raw.modified_at,
        raw_content=raw.content,
        metadata=raw.metadata,
        evidence=[
            Evidence(
                identity=f"evidence:memory:{entry_id}",
                source=source,
                reference=str(raw.path),
                captured_at=raw.modified_at,
                excerpt=raw.content[:EXCERPT_LENGTH],
            )
        ],
    )
