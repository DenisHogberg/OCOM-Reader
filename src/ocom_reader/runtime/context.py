"""RuntimeContext — wires already-existing components together.

Not a new component with its own behavior: a plain container that
constructs and holds one instance of each existing collaborator
(`Storage`, `ClassificationEngine`, `IdentityResolver`, `ObjectRegistry`,
`EvidenceAggregator`, `AnswerComposer`) so `pipeline.py` doesn't have to
re-construct them at every call site. No decision logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocom_reader.agent.evidence import EvidenceAggregator
from ocom_reader.agent.answer import AnswerComposer
from ocom_reader.agent.registry import ObjectRegistry
from ocom_reader.identity.resolver import IdentityResolver
from ocom_reader.intelligence.classification import ClassificationEngine
from ocom_reader.interfaces.storage import Storage


@dataclass
class RuntimeContext:
    storage: Storage
    classification_engine: ClassificationEngine
    identity_resolver: IdentityResolver
    registry: ObjectRegistry
    evidence_aggregator: EvidenceAggregator
    answer_composer: AnswerComposer

    @classmethod
    def build(cls, storage: Storage) -> "RuntimeContext":
        return cls(
            storage=storage,
            classification_engine=ClassificationEngine(),
            identity_resolver=IdentityResolver(),
            registry=ObjectRegistry(storage),
            evidence_aggregator=EvidenceAggregator(),
            answer_composer=AnswerComposer(),
        )
