"""DocumentLoader — reads a discovered file's content and filesystem metadata.

Deliberately independent from adapters/filesystem_documentation.py's
RawDocument: that type is scoped to feeding a Normalizer toward an
OCOMObject (ADR-001) — a fundamentally different pipeline this
milestone explicitly does not join ("no object extraction"). This
loader produces its own, unrelated raw shape rather than reusing or
depending on that one, so a future change to either pipeline cannot
silently break the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LoadedDocument:
    path: Path
    content: str
    last_modified: datetime


class DocumentLoadError(Exception):
    """Raised when a discovered file cannot be loaded as UTF-8 text."""


class DocumentLoader:
    def load(self, path: Path) -> LoadedDocument:
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise DocumentLoadError(f"{path}: {exc}") from exc

        stat = path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return LoadedDocument(path=path, content=content, last_modified=last_modified)
