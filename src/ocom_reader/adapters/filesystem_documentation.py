"""Filesystem Documentation Adapter.

Reads a local folder of documentation files. Returns raw data only —
content, file path, timestamp, basic metadata. Nothing here knows what
an OCOMObject is, extracts entities, calls an LLM, or normalizes
anything. That boundary belongs entirely to the Normalizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from ocom_reader.interfaces.adapter import Adapter

DEFAULT_EXTENSIONS: Sequence[str] = (".md", ".txt")


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
