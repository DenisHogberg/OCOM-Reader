"""Composer data models.

`ComposedAnswer` is deliberately not named `Answer` — that name is
already taken by `ocom_reader.agent.answer.Answer`, an unrelated model
from the OCOM domain-object Agent pipeline (Evidence-grounded answers
about extracted OCOM Objects). This module's `ComposedAnswer` answers a
different question: which of this repository's own documentation files
are relevant to a query, and how they relate. Same vocabulary, two
independent pipelines — see composer/answer_composer.py's module
docstring and MILESTONE-009-010.md for the full disambiguation.

Every field here is either a pointer (`registry_id`, `document_id`),
already-known text copied at presentation time from `RepositoryIndex`
(`title`, `path`), or a fixed-template string (`reasons`, `answer`) —
never generated prose. `evidence` reuses the word in its ordinary
English sense ("documents that support this answer"), not
`core.Evidence`/`agent.evidence.Evidence` — no relation to those models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentRef(BaseModel):
    registry_id: str
    document_id: str
    title: str
    path: str
    document_type: str


class ExplainedDocument(BaseModel):
    document: DocumentRef
    reasons: list[str] = Field(default_factory=list)
    score: float = 0.0


class ComposedAnswer(BaseModel):
    query: str
    answer: str
    evidence: list[ExplainedDocument] = Field(default_factory=list)
    related_documents: list[ExplainedDocument] = Field(default_factory=list)
    reading_order: list[DocumentRef] = Field(default_factory=list)
    grounded: bool
