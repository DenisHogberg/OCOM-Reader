"""OCOM Agent v0.1 — first vertical slice.

Question -> Object -> Evidence -> Answer, no LLM, no embeddings, no
vector search. Storage is the only source of truth, walked directly
through ObjectRegistry's keyword search.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ocom_reader.agent.answer import AnswerComposer
from ocom_reader.agent.evidence import EvidenceAggregator
from ocom_reader.agent.query import Query
from ocom_reader.agent.registry import ObjectRegistry
from ocom_reader.core.evidence import Evidence
from ocom_reader.core.object import OCOMObject
from ocom_reader.storage.local_storage import LocalJSONStorage


def _run(storage: LocalJSONStorage, question: str):
    registry = ObjectRegistry(storage)
    aggregator = EvidenceAggregator()
    composer = AnswerComposer()

    candidates = registry.find_candidates(Query(text=question))
    context = aggregator.aggregate(candidates)
    return composer.compose(context)


def test_question_object_evidence_answer_vertical_slice(tmp_path: Path) -> None:
    storage = LocalJSONStorage(tmp_path / "data")
    storage.save(
        OCOMObject(
            identity="concept:ocom-object",
            object_type="Concept",
            metadata={"identity": {"name": "OCOM Object"}},
            evidence=[
                Evidence(
                    identity="evidence:object-md",
                    source="filesystem-documentation",
                    reference="Object.md",
                    captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
                    excerpt="OCOM Object represents...",
                )
            ],
        )
    )

    answer = _run(storage, "What is OCOM Object?")

    assert answer.grounded is True
    assert "OCOM Object represents..." in answer.text
    assert "Object.md" in answer.text
    assert answer.sources == ["Object.md"]


def test_answer_cites_evidence_from_every_matching_object(tmp_path: Path) -> None:
    storage = LocalJSONStorage(tmp_path / "data")
    storage.save(
        OCOMObject(
            identity="doc:object-md",
            object_type="Concept",
            metadata={"identity": {"name": "OCOM Object"}},
            evidence=[
                Evidence(
                    identity="evidence:object-md",
                    source="filesystem-documentation",
                    reference="Object.md",
                    captured_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
                    excerpt="OCOM Object represents...",
                )
            ],
        )
    )
    storage.save(
        OCOMObject(
            identity="doc:architecture-md",
            object_type="Concept",
            metadata={"identity": {"name": "OCOM Object Architecture"}},
            evidence=[
                Evidence(
                    identity="evidence:architecture-md",
                    source="filesystem-documentation",
                    reference="Architecture.md",
                    captured_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
                    excerpt="The Object Architecture describes...",
                )
            ],
        )
    )

    answer = _run(storage, "What is OCOM Object?")

    assert answer.grounded is True
    assert set(answer.sources) == {"Object.md", "Architecture.md"}


def test_answer_is_not_grounded_when_no_evidence_found(tmp_path: Path) -> None:
    storage = LocalJSONStorage(tmp_path / "data")

    answer = _run(storage, "What is a nonexistent concept?")

    assert answer.grounded is False
    assert answer.sources == []
    assert answer.text == "No evidence found to answer this question."
