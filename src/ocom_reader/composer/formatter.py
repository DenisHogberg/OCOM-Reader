"""Formatting only — turns already-structured data into text.

`explain_reason` is a fixed kind -> template lookup, the same
"dictionary, not generation" discipline `ranking.py`'s `SCORE_WEIGHTS`
already uses for scores. `render` lays out a `ComposedAnswer` into the
four-section shape every answer uses: Answer, Evidence, Related
Documents, Recommended Reading Order — always present, in that order,
so every answer has the same shape regardless of content.
"""

from __future__ import annotations

from ocom_reader.composer.models import ComposedAnswer, ExplainedDocument
from ocom_reader.retrieval.models import MatchReason

REASON_TEMPLATES: dict[str, str] = {
    "title_match": "Title match: {detail}",
    "heading_match": "Heading match: {detail}",
    "preview_match": "Preview match: {detail}",
    "builds_on": "Related via builds_on to {detail}",
    "references": "Related via references to {detail}",
    "architecture_sequence": "Related via architecture_sequence to {detail}",
}


def explain_reason(reason: MatchReason) -> str:
    template = REASON_TEMPLATES.get(reason.kind, "{kind}: {detail}")
    return template.format(kind=reason.kind, detail=reason.detail)


def _render_document_line(doc: ExplainedDocument) -> str:
    reasons = ", ".join(doc.reasons) if doc.reasons else "(no recorded reason)"
    return f"  - {doc.document.title} ({doc.document.path}) [score {doc.score:g}] — {reasons}"


def render(answer: ComposedAnswer) -> str:
    lines = [f"Question: {answer.query}", "", "Answer", f"  {answer.answer}", ""]

    lines.append("Evidence")
    if answer.evidence:
        lines.extend(_render_document_line(doc) for doc in answer.evidence)
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Related Documents")
    if answer.related_documents:
        lines.extend(_render_document_line(doc) for doc in answer.related_documents)
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Recommended Reading Order")
    if answer.reading_order:
        lines.extend(f"  {i}. {doc.title} ({doc.path})" for i, doc in enumerate(answer.reading_order, start=1))
    else:
        lines.append("  (not applicable)")

    return "\n".join(lines)
