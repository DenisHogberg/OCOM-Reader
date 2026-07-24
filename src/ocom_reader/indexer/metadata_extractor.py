"""MetadataExtractor — turns a loaded, parsed document into per-document
index metadata: a stable id, a document_type classified from its path,
and a content hash for duplicate detection.

document_type classification is a small, fixed rule table — the same
"dictionary, not inference" discipline already used by
intelligence/classification.py, applied here to file paths instead of
object names. Cross-document metadata (inbound_references, duplicate
grouping) needs the whole index and is not this component's job — see
RepositoryIndexBuilder.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


class MetadataExtractor:
    def document_id(self, relative_path: Path) -> str:
        return relative_path.as_posix()

    def document_type(self, relative_path: Path) -> str:
        name = relative_path.name
        parts = relative_path.parts

        if name == "README.md":
            return "README"
        if name.startswith("ADR-"):
            return "ADR"
        if name.startswith("MILESTONE-"):
            return "Milestone"
        if "architecture" in parts or name.startswith("OCOM-"):
            return "Architecture"
        return "Documentation"

    def content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
