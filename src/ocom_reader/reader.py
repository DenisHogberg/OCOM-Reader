"""Reader — the public facade over the full documentation pipeline.

Repository -> RepositoryIndex (M006) -> KnowledgeRegistry (M007) ->
RetrievalEngine (M008) -> AnswerComposer (M009-010). Reader owns
exactly one instance of each, built once at construction — the same
"build once, query many times, no incremental mutation" pattern
RegistryBuilder and RetrievalEngine already use. It adds no new
matching, ranking, or composition logic of its own; every method is a
direct, one-line delegation to an already-tested component.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.composer.answer_composer import AnswerComposer
from ocom_reader.composer.models import ComposedAnswer, ExplainedDocument
from ocom_reader.indexer.index_builder import RepositoryIndexBuilder
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry_builder import RegistryBuilder
from ocom_reader.retrieval.models import RetrievalMatch
from ocom_reader.retrieval.retrieval_engine import RetrievalEngine


class Reader:
    def __init__(self, repository_root: Path) -> None:
        self._index = RepositoryIndexBuilder(repository_root).build()
        self._registry = RegistryBuilder().build(self._index)
        self._engine = RetrievalEngine(self._index, self._registry)
        self._composer = AnswerComposer(self._index, self._registry)

    def answer(self, query: str) -> ComposedAnswer:
        return self._composer.compose(self._engine.retrieve(query))

    def search(self, query: str) -> list[RetrievalMatch]:
        return self._engine.retrieve(query).matches

    def related(self, registry_id: str) -> list[RegistryEntry]:
        return self._engine.related(registry_id)

    def explain(self, query: str) -> list[ExplainedDocument]:
        answer = self.answer(query)
        return answer.evidence + answer.related_documents
