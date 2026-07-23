"""AnswerComposer — template-based, no LLM.

This is the one component this entire vertical slice exists to prove:
the agent answers only from Evidence. If UnifiedEvidenceContext carries
no evidence, the composer refuses to answer rather than describing an
object from its metadata alone — there is no fallback path that
produces an ungrounded statement.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ocom_reader.agent.evidence import UnifiedEvidenceContext

NOT_GROUNDED_TEXT = "No evidence found to answer this question."


class Answer(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)
    grounded: bool


class AnswerComposer:
    def compose(self, context: UnifiedEvidenceContext) -> Answer:
        if not context.evidence:
            return Answer(text=NOT_GROUNDED_TEXT, sources=[], grounded=False)

        statements = [e.excerpt for e in context.evidence if e.excerpt]
        sources = [e.reference for e in context.evidence]

        body = "\n\n".join(statements) if statements else "(no supporting excerpt recorded)"
        source_lines = "\n".join(f"- {source}" for source in sources)

        text = f"Answer:\n\nAccording to OCOM evidence:\n\n{body}\n\nSources:\n{source_lines}"
        return Answer(text=text, sources=sources, grounded=True)
