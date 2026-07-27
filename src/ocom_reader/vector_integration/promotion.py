"""Reader M04 — Promotion Review UI (`READER_M04_DESIGN.md`).

Reader MUST NOT infer new semantic objects. Reader MAY group, sort, and
visualize contracted Vector data. Reader MUST NOT create Promotion
Candidates, Promotion Scores, Promotion Labels, or any derived workflow
state absent from the Vector Contract (the Design Principle this module is
built against).

Concretely: this groups Statements by the single, already-decided,
already-contracted `statement_kind` field. It never reasons about
`detected_signals` combinations to invent a candidate label — that would
reimplement Vector's own (unpublished, analysis-only)
`M05_PROMOTION_READINESS.md` signal-combination table inside Reader, making
Reader a second implementation of Vector's business logic. `detected_signals`
is shown per-Statement (via the existing `render_statement()`) for context
only, never used for grouping here.

Callers MUST pass `statements` already filtered through
`navigation.filter_to_current_meetings(statements, meetings)`. Without it,
this inherits the exact reindex-duplication bug M03 found and fixed for
Object Navigation (the same real Meeting, reprocessed several times by
Vector's own idempotent-import pipeline, would otherwise appear as several
duplicate Meeting sections here too).
"""

from __future__ import annotations

from ocom_reader.vector_integration.models import VectorMeeting, VectorStatement
from ocom_reader.vector_integration.signals import render_statement

# The six closed statement_kind values, per vector-reader-contract.md /
# models.KNOWN_STATEMENT_KINDS. Fixed rendering order — Task/Decision/Risk
# first (the actual promotion-relevant kinds), then Metric, then the two
# non-actionable kinds last.
REVIEW_GROUPS = ("task_signal", "decision_signal", "risk_signal", "metric", "fact", "other")

# "unclassified" is not a real statement_kind value — it's what a Statement
# with statement_kind=None falls into (data absence). Always shown alongside
# the six real kinds, for the same reason render_signal_browser always shows
# all five signal groups: a review queue that could silently omit a group
# isn't a complete picture, it's a hidden filter.
UNCLASSIFIED = "unclassified"
ALWAYS_SHOWN_GROUPS = REVIEW_GROUPS + (UNCLASSIFIED,)

STATEMENT_KIND_DISPLAY = {
    "task_signal": "Task",
    "decision_signal": "Decision",
    "risk_signal": "Risk",
    "metric": "Metric",
    "fact": "Fact",
    "other": "Other",
    UNCLASSIFIED: "Unclassified",
}

UNKNOWN_MEETING_LABEL = "(unknown meeting)"


def group_by_statement_kind(statements: list[VectorStatement]) -> dict[str, list[VectorStatement]]:
    """Buckets by the exact, literal statement_kind value already on each
    Statement — no re-classification, no combination logic. A Statement with
    no statement_kind at all goes to UNCLASSIFIED, never merged into "other"
    (a real classifier output, not a stand-in for missing data). A
    statement_kind value outside the six known ones (a future Vector enum
    extension) gets its own ad-hoc bucket keyed by that literal value —
    never dropped, never coerced into an existing group."""
    grouped: dict[str, list[VectorStatement]] = {}
    for s in statements:
        key = s.statement_kind if s.statement_kind is not None else UNCLASSIFIED
        grouped.setdefault(key, []).append(s)
    return grouped


def _timestamp_seconds(timestamp: str) -> float:
    """Parses Vector's zero-padded `MM:SS` Statement.timestamp into seconds
    for numeric comparison. A raw string compare breaks past 99 minutes
    ("100:00" < "99:59" lexicographically) — real Vector meetings already
    run past 30 minutes, so this isn't a remote hypothetical. A malformed
    value (never seen in real data, but not schema-enforced) sorts last
    within its Meeting rather than raising — this function must never crash
    a review render over one oddly-formatted Statement."""
    try:
        minutes, seconds = timestamp.split(":")
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return float("inf")


def _statement_sort_key(stmt: VectorStatement) -> tuple[float, str]:
    """Chronological within a Meeting, tie-broken by Statement.id — so two
    Statements at the same timestamp (or both with an unparseable one) still
    render in a fixed, reproducible order across runs, not whatever order
    happened to fall out of the filesystem's rglob."""
    return (_timestamp_seconds(stmt.timestamp), stmt.id)


def _meeting_sections(
    statements: list[VectorStatement], meetings: list[VectorMeeting]
) -> list[tuple[str, list[VectorStatement]]]:
    """Partitions statements (already belonging to one statement_kind group)
    into ordered (Meeting title, ordered Statements) sections: one per
    resolved Meeting, sorted by meeting_date (undated last), tie-broken by
    Meeting id for determinism when two Meetings share a date; then a final
    UNKNOWN_MEETING_LABEL section for any Statement whose meeting_ref
    doesn't resolve against the given Meetings — never dropped, same
    tolerance policy as navigation.mentions()'s unresolved-reference
    handling."""
    by_id = {m.id: m for m in meetings}
    grouped: dict[str, list[VectorStatement]] = {}
    unresolved: list[VectorStatement] = []
    for s in statements:
        if s.meeting_ref in by_id:
            grouped.setdefault(s.meeting_ref, []).append(s)
        else:
            unresolved.append(s)

    def meeting_sort_key(meeting_id: str) -> tuple[bool, str, str]:
        meeting = by_id[meeting_id]
        return (meeting.meeting_date is None, meeting.meeting_date or "", meeting_id)

    sections = [
        (by_id[meeting_id].title, sorted(grouped[meeting_id], key=_statement_sort_key))
        for meeting_id in sorted(grouped, key=meeting_sort_key)
    ]
    if unresolved:
        sections.append((UNKNOWN_MEETING_LABEL, sorted(unresolved, key=_statement_sort_key)))
    return sections


def render_promotion_review(
    statements: list[VectorStatement], meetings: list[VectorMeeting]
) -> str:
    """Reader M04 Public API — the Promotion Review block. All seven
    ALWAYS_SHOWN_GROUPS render in fixed order, even at zero count (same
    consistency discipline as render_signal_browser). Any statement_kind
    value outside those seven (a future Vector enum extension, never seen in
    real data today) is appended afterward, sorted alphabetically, but only
    when actually present — there is no way to pre-list infinitely many
    hypothetical future values the way the seven known ones can be.

    See this module's docstring: `statements` must already be filtered
    through navigation.filter_to_current_meetings — this function does not
    do that itself, so a caller skipping it will see duplicate Meeting
    sections for a reprocessed transcript."""
    grouped = group_by_statement_kind(statements)
    extra_groups = sorted(k for k in grouped if k not in ALWAYS_SHOWN_GROUPS)
    ordered_keys = list(ALWAYS_SHOWN_GROUPS) + extra_groups

    blocks = []
    for key in ordered_keys:
        matches = grouped.get(key, [])
        label = STATEMENT_KIND_DISPLAY.get(key, key)
        blocks.append(f"{label.upper()} ({len(matches)})")
        blocks.append("")
        if matches:
            for meeting_title, ordered in _meeting_sections(matches, meetings):
                blocks.append(meeting_title)
                blocks.append("")
                for stmt in ordered:
                    blocks.append(render_statement(stmt))
                    blocks.append("")
        else:
            blocks.append("(none)")
            blocks.append("")
    return "\n".join(blocks).rstrip("\n")
