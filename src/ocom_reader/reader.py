"""Reader — the public facade over the full documentation pipeline.

Repository -> RepositoryIndex (M006) -> KnowledgeRegistry (M007) ->
RetrievalEngine (M008) -> AnswerComposer (M009-010), now persisted to
`.ocom/` by default (M012). Reader owns exactly one instance of each,
built once at construction — the same "build once, query many times,
no incremental mutation" pattern RegistryBuilder and RetrievalEngine
already use. It adds no new matching, ranking, or composition logic of
its own; every method is a direct, one-line delegation to an
already-tested component.

`use_persistence=True` (default): the index comes from `RepositoryLoader`
(reused via `.ocom/` when present and unchanged, otherwise freshly
built), `KnowledgeRegistry` is always rebuilt fresh from whatever index
is in hand (cheap and deterministic — never loaded back from disk, so
there is no index/registry staleness question), and the resulting
Index+Registry snapshot is written to `.ocom/` — a new, real disk
write where none existed before M012, and the intended behavior of
"Persistent Storage," not an accidental side effect. `use_persistence=False`
preserves M009-010's original behavior exactly: pure in-memory build,
zero disk I/O.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.composer.answer_composer import AnswerComposer
from ocom_reader.composer.models import ComposedAnswer, ExplainedDocument
from ocom_reader.indexer.index_builder import RepositoryIndexBuilder
from ocom_reader.loader.repository_loader import RepositoryLoader
from ocom_reader.persistence.store import PersistentStore
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.registry.registry_builder import RegistryBuilder
from ocom_reader.retrieval.models import RetrievalMatch
from ocom_reader.retrieval.retrieval_engine import RetrievalEngine


class Reader:
    def __init__(self, repository_root: Path, use_persistence: bool = True) -> None:
        repository_root = Path(repository_root)
        if use_persistence:
            self._index = RepositoryLoader().load(repository_root)
        else:
            self._index = RepositoryIndexBuilder(repository_root).build()

        self._registry = RegistryBuilder().build(self._index)

        if use_persistence:
            PersistentStore(repository_root).save(self._index, self._registry)

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
