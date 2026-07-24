"""Retrieval Engine — deterministic search and ranking over
RepositoryIndex + KnowledgeRegistry. Finds and ranks; does not answer.
See docs/architecture/MILESTONE-008.md.
"""

from ocom_reader.retrieval.models import MatchReason, QueryObject, RetrievalMatch, RetrievalResult
from ocom_reader.retrieval.query_parser import QueryParser
from ocom_reader.retrieval.ranking import Ranker
from ocom_reader.retrieval.retrieval_engine import RetrievalEngine

__all__ = [
    "QueryObject",
    "MatchReason",
    "RetrievalMatch",
    "RetrievalResult",
    "QueryParser",
    "Ranker",
    "RetrievalEngine",
]
