"""AnswerComposer — RetrievalResult -> ComposedAnswer, nothing else.

Not `ocom_reader.agent.answer.AnswerComposer` — that composer belongs to
the unrelated OCOM domain-object Agent pipeline (Evidence-grounded
answers built from `UnifiedEvidenceContext`). This composer answers a
different question, over a different pipeline (Repository -> Index ->
Registry -> Retrieval, M006-M008). Never import both into the same
scope unqualified — see composer/models.py and MILESTONE-009-010.md.

Composer never decides what is relevant. It has no `.search()`,
`.rank()`, or `.filter()` call anywhere in this file. Every document
that appears in a `ComposedAnswer` was already selected and ordered by
`RetrievalEngine`/`Ranker` (M008) before this module ever sees it:

  - Grouping into `evidence` vs `related_documents` is a straight
    reclassification of a fact `RetrievalEngine` already computed (a
    match either has a text-match reason or it doesn't) — not a new
    relevance judgment.
  - Order within each group is exactly `RetrievalResult.matches`'
    order, untouched.
  - `reading_order` is a deterministic topological sort of relation
    edges that already exist between documents already in the result
    set — it can reorder, but never add or remove, a document.
  - The only thing resembling "filtering" is a defensive dedup of
    exact-duplicate registry_ids (see `_deduplicate`), guarding against
    a malformed `RetrievalResult` passed by a caller other than
    `Reader` — not a relevance filter. `RetrievalResult` is expected to
    already be duplicate-free per M008's own tests.

`RepositoryIndex` and `KnowledgeRegistry` are held read-only, purely to
resolve pointers (`document_id -> title/path`, and existing relation
edges) at presentation time — the same "resolve at the edge, never
copy upstream" discipline `EvidencePresentationMapper` used in M005.
Neither is ever mutated, and neither is ever searched.
"""

from __future__ import annotations

from ocom_reader.composer.formatter import explain_reason
from ocom_reader.composer.models import ComposedAnswer, DocumentRef, ExplainedDocument
from ocom_reader.indexer.models import RepositoryIndex
from ocom_reader.registry.registry import KnowledgeRegistry
from ocom_reader.retrieval.models import RetrievalMatch, RetrievalResult

TEXT_REASON_KINDS = {"title_match", "identifier_match", "heading_match", "preview_match"}
# "importance" (M014) is deliberately excluded — it's a modifier present
# on both evidence and related documents alike, never itself a reason a
# document counts as directly matching the query.
ORDERING_RELATION_KINDS = {"builds_on", "architecture_sequence"}


class AnswerComposer:
    def __init__(self, index: RepositoryIndex, registry: KnowledgeRegistry) -> None:
        self._index = index
        self._registry = registry

    def compose(self, result: RetrievalResult) -> ComposedAnswer:
        matches = self._deduplicate(result.matches)

        evidence_matches = [m for m in matches if self._is_primary(m)]
        related_matches = [m for m in matches if not self._is_primary(m)]

        evidence = [self._to_explained(m) for m in evidence_matches]
        related_documents = [self._to_explained(m) for m in related_matches]

        reading_order = self._reading_order(evidence + related_documents)

        return ComposedAnswer(
            query=result.query.raw,
            answer=self._answer_text(result.query.raw, evidence),
            evidence=evidence,
            related_documents=related_documents,
            reading_order=reading_order,
            grounded=bool(evidence),
        )

    def _is_primary(self, match: RetrievalMatch) -> bool:
        return any(reason.kind in TEXT_REASON_KINDS for reason in match.reasons)

    def _deduplicate(self, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
        seen: dict[str, RetrievalMatch] = {}
        for match in matches:
            registry_id = match.entry.registry_id
            if registry_id not in seen:
                seen[registry_id] = match
            else:
                merged_reasons = seen[registry_id].reasons + [
                    r for r in match.reasons if r not in seen[registry_id].reasons
                ]
                seen[registry_id] = seen[registry_id].model_copy(update={"reasons": merged_reasons})
        return list(seen.values())

    def _to_explained(self, match: RetrievalMatch) -> ExplainedDocument:
        document = self._document_ref(match.entry.registry_id, match.entry.document_id, match.entry.entry_type)
        reasons = [explain_reason(reason) for reason in match.reasons]
        return ExplainedDocument(document=document, reasons=reasons, score=match.score)

    def _document_ref(self, registry_id: str, document_id: str, entry_type: str) -> DocumentRef:
        indexed = self._index.get(document_id)
        title = indexed.title if indexed is not None else document_id
        path = indexed.path if indexed is not None else document_id
        preview = indexed.preview if indexed is not None else ""
        return DocumentRef(
            registry_id=registry_id,
            document_id=document_id,
            title=title,
            path=path,
            document_type=entry_type,
            preview=preview,
        )

    def _answer_text(self, query: str, evidence: list[ExplainedDocument]) -> str:
        if not evidence:
            return f'No documentation found for "{query}".'
        top_title = evidence[0].document.title
        count = len(evidence)
        return f'Found {count} relevant document(s) for "{query}". Most relevant: "{top_title}".'

    def _reading_order(self, documents: list[ExplainedDocument]) -> list[DocumentRef]:
        by_id = {doc.document.registry_id: doc.document for doc in documents}
        node_ids = set(by_id.keys())

        edges: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        for relation in self._registry.relations:
            if relation.relation_type not in ORDERING_RELATION_KINDS:
                continue
            if relation.source_id not in node_ids or relation.target_id not in node_ids:
                continue
            if relation.relation_type == "builds_on":
                # source builds_on target -> target (the base) is read first.
                edges[relation.target_id].add(relation.source_id)
            else:  # architecture_sequence: source is earlier, target is later.
                edges[relation.source_id].add(relation.target_id)

        if not any(edges.values()):
            return []

        return self._topological_sort(by_id, edges)

    def _topological_sort(
        self, by_id: dict[str, DocumentRef], edges: dict[str, set[str]]
    ) -> list[DocumentRef]:
        in_degree = {node_id: 0 for node_id in by_id}
        for successors in edges.values():
            for successor in successors:
                in_degree[successor] += 1

        ready = sorted(node_id for node_id, degree in in_degree.items() if degree == 0)
        ordered: list[str] = []

        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for successor in sorted(edges[node_id]):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    ready.append(successor)
            ready.sort()

        if len(ordered) != len(by_id):
            return []  # cycle detected — do not misrepresent the data

        return [by_id[node_id] for node_id in ordered]
