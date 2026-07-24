"""DocumentIndexEntry / RepositoryIndex — the data this subsystem exists to produce.

Deliberately not an OCOMObject: this milestone's own scope excludes
"object extraction" — the Repository Indexer answers "what documents
exist and where," not "what OCOM Objects do they describe." Building
an index of OCOMObjects from documentation is a later, separate
concern (semantic interpretation, explicitly out of scope here).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Heading(BaseModel):
    level: int
    text: str


class DocumentIndexEntry(BaseModel):
    id: str
    path: str
    title: str
    document_type: str
    last_modified: datetime
    headings: list[Heading] = Field(default_factory=list)
    internal_links: list[str] = Field(default_factory=list)
    builds_on_links: list[str] = Field(default_factory=list)
    outbound_references: list[str] = Field(default_factory=list)
    inbound_references: list[str] = Field(default_factory=list)
    preview: str = ""
    content_hash: str = ""


class InvalidDocument(BaseModel):
    path: str
    reason: str


class RepositoryIndex(BaseModel):
    entries: list[DocumentIndexEntry] = Field(default_factory=list)
    invalid: list[InvalidDocument] = Field(default_factory=list)
    duplicates: list[list[str]] = Field(default_factory=list)

    def get(self, document_id: str) -> Optional[DocumentIndexEntry]:
        for entry in self.entries:
            if entry.id == document_id:
                return entry
        return None

    def by_type(self, document_type: str) -> list[DocumentIndexEntry]:
        return [entry for entry in self.entries if entry.document_type == document_type]

    def all(self) -> list[DocumentIndexEntry]:
        return list(self.entries)
