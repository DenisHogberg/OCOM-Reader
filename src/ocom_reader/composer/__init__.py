"""Composer — turns a RetrievalResult (M008) into a ComposedAnswer.

Composer never searches, ranks, or filters — see answer_composer.py's
module docstring for the full invariant. See docs/architecture/MILESTONE-009-010.md.
"""

from ocom_reader.composer.answer_composer import AnswerComposer
from ocom_reader.composer.formatter import explain_reason, render
from ocom_reader.composer.models import ComposedAnswer, DocumentRef, ExplainedDocument

__all__ = [
    "AnswerComposer",
    "ComposedAnswer",
    "DocumentRef",
    "ExplainedDocument",
    "explain_reason",
    "render",
]
