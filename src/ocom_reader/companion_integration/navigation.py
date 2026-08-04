"""Reader M03 — Object Navigation: Object View, reverse navigation from a
Statement to the objects it mentions, cross-meeting view, a text-only
relationship browser, and an entity timeline.

Scope note, stated once here rather than repeated on every function: none of
this is covered by docs/contracts/companion-reader-contract.md v1.0, which is
Statement-only. This module reads Companion's common object frontmatter
(id/type/title/relationships/references/tags — Companion's own docs/object-model.md)
and, for the timeline specifically, Meeting.meeting_date (see
models.CompanionMeeting's docstring for why that one field is a deliberate,
flagged exception). See READER_M03.md for the explicit recommendation that
Companion formally publish a second contract (or extend the existing one) to
cover this.

Everything here is read-only. It also inherits M01's key limitation
honestly, not silently: Companion's real data has zero populated `relationships`
and zero `alias:` tags on any of its 6 real objects today (verified directly,
not assumed) — Object View's Aliases/Relationships sections and the
Relationship Browser are exercised in tests_companion_integration.py against
synthetic fixtures for that reason, alongside real-data tests for the parts
(Linked Statements, Mentions, Cross-Meeting View, Timeline) that Companion's
real `references` data already supports.
"""

from __future__ import annotations

from typing import Optional

from ocom_reader.companion_integration.loader import find_current_meetings
from ocom_reader.companion_integration.models import CompanionMeeting, CompanionObject, CompanionStatement


def filter_to_current_meetings(
    statements: list[CompanionStatement], meetings: list[CompanionMeeting]
) -> list[CompanionStatement]:
    """Drop Statements belonging to a superseded reindex run of the same
    real-world meeting. Discovered necessary by actually running `companion
    object`/`mentioned-in`/`timeline` against Companion's real repository root
    (which contains ~6 reprocessing runs of the same meeting across
    M03-M07, same source_hash, different parser_version): without this, a
    single real meeting a Partner was mentioned in shows up as 6 separate
    "meetings" with the same title, and Linked Statements over-counts by the
    same factor. Reuses loader.find_current_meetings — the identical
    supersedes-chain resolution Companion's own pipeline already relies on for
    idempotent import — rather than inventing a second notion of "current"
    here. Object Navigation callers (Object View, Cross-Meeting View, Entity
    Timeline) should filter through this before aggregating across meetings;
    render_mentions (reverse navigation from one already-selected Statement)
    is unaffected, since it never aggregates across meetings in the first
    place."""
    current_ids = {m.id for m in find_current_meetings(meetings)}
    return [s for s in statements if s.meeting_ref in current_ids]


def find_object(objects: list[CompanionObject], object_id: str) -> Optional[CompanionObject]:
    return next((o for o in objects if o.id == object_id), None)


def linked_statements(object_id: str, statements: list[CompanionStatement]) -> list[CompanionStatement]:
    """Statements whose `references` include this object id — the same
    `references` field M01 already models on CompanionStatement, just read from
    the other direction (object -> mentioning Statements, not Statement ->
    referenced objects)."""
    return [
        s for s in statements
        if any(ref.get("target") == object_id for ref in s.references)
    ]


def linked_meeting_ids(statements: list[CompanionStatement]) -> list[str]:
    """Distinct Meeting ids referenced by these Statements, in first-seen
    order (not sorted — callers needing chronological order should use
    render_entity_timeline, which resolves real dates). `seen` is a set for
    O(1) membership (a list here would make this O(n*m) — n statements times
    m distinct meetings — instead of O(n)); a separate list preserves the
    order a set can't guarantee.

    Takes an already-filtered Statement list (typically the output of
    linked_statements()) rather than an object id, so a caller who already
    has that list doesn't have to filter it twice — see render_object_view
    below for why that mattered."""
    seen: set[str] = set()
    ids: list[str] = []
    for s in statements:
        if s.meeting_ref not in seen:
            seen.add(s.meeting_ref)
            ids.append(s.meeting_ref)
    return ids


def render_object_view(
    obj: CompanionObject, statements: list[CompanionStatement], objects: list[CompanionObject]
) -> str:
    """M03 Task 1 — the Object View block. `objects` (Reader M05 — Evidence view)
    is every loaded object from the same root, used only to resolve `obj.evidence`
    ids to their Evidence objects — the exact same by-id resolution `mentions()`
    already uses for `references`, not a new pattern."""
    linked = linked_statements(obj.id, statements)
    meeting_ids = linked_meeting_ids(linked)
    lines = [
        "Object", "",
        "Type:", obj.type, "",
        "Name:", obj.title, "",
        "Linked Statements:", str(len(linked)), "",
        "Meetings:", str(len(meeting_ids)), "",
        "Aliases:",
    ]
    aliases = obj.aliases()
    lines.extend(aliases if aliases else ["(none)"])
    lines += ["", "Relationships:"]
    if obj.relationships:
        lines.extend(
            f"{rel.get('type', '?')} → {rel.get('target', '?')}" for rel in obj.relationships
        )
    else:
        lines.append("(none)")
    lines += ["", "Evidence:"]
    by_id = {o.id: o for o in objects}
    resolved_evidence = [by_id[eid] for eid in obj.evidence if eid in by_id]
    if resolved_evidence:
        lines.extend(
            f"{e.source_type or '(source type unknown)'} — {e.id}" for e in resolved_evidence
        )
    else:
        lines.append("(none)")
    return "\n".join(lines)


def mentions(stmt: CompanionStatement, objects: list[CompanionObject]) -> list[CompanionObject]:
    """M03 Task 2 (Reverse Navigation) — the objects this Statement's
    `references` resolve to, in the order they appear in `references`.
    A `references` entry whose target isn't found among `objects` (either
    genuinely unresolved, or the object simply wasn't loaded from this root)
    is silently skipped, not an error — same tolerance policy as the rest of
    this package."""
    by_id = {o.id: o for o in objects}
    found = []
    for ref in stmt.references:
        obj = by_id.get(ref.get("target"))
        if obj is not None:
            found.append(obj)
    return found


def render_mentions(stmt: CompanionStatement, objects: list[CompanionObject]) -> str:
    found = mentions(stmt, objects)
    lines = ["Mentions", ""]
    lines.extend(f"✓ {o.title}" for o in found) if found else lines.append("(none)")
    return "\n".join(lines)


def meetings_mentioning(
    obj: CompanionObject, statements: list[CompanionStatement], meetings: list[CompanionMeeting]
) -> list[CompanionMeeting]:
    """M03 Task 3 (Cross-Meeting View) — every Meeting whose Statements
    mention this object, resolved from ids to the actual Meeting objects."""
    by_id = {m.id: m for m in meetings}
    ids = linked_meeting_ids(linked_statements(obj.id, statements))
    return [by_id[i] for i in ids if i in by_id]


def render_cross_meeting_view(
    obj: CompanionObject, statements: list[CompanionStatement], meetings: list[CompanionMeeting]
) -> str:
    found = meetings_mentioning(obj, statements, meetings)
    lines = [obj.title, "", "mentioned in", ""]
    lines.extend(m.title for m in found) if found else lines.append("(none)")
    return "\n".join(lines)


def render_relationship_tree(
    start: CompanionObject, objects: list[CompanionObject], max_depth: int = 6
) -> str:
    """M03 Task 4 (Relationship Browser) — a plain text tree, no graphical
    visualization, walking `relationships[].target` from `start`. Generic:
    does not hardcode any relationship type name (Companion's own vocabulary is
    open-ended per docs/relationships-and-references.md — "works_with" in
    the milestone's own example isn't in Companion's documented starter list,
    and this function doesn't need it to be). Cycle-safe: a relationship
    loop (A -> B -> A) stops the walk rather than recursing forever, and
    `max_depth` is a second, independent safety bound."""
    by_id = {o.id: o for o in objects}
    lines: list[str] = []
    visited: set[str] = set()

    def walk(obj: CompanionObject, depth: int) -> None:
        lines.append(obj.type.capitalize())
        if obj.id in visited or depth >= max_depth:
            return
        visited.add(obj.id)
        for rel in obj.relationships:
            target = by_id.get(rel.get("target"))
            if target is None:
                continue
            lines.append("")
            lines.append("↓")
            lines.append("")
            lines.append(rel.get("type", "?"))
            lines.append("")
            lines.append("↓")
            lines.append("")
            walk(target, depth + 1)

    walk(start, 0)
    return "\n".join(lines)


def render_entity_timeline(
    obj: CompanionObject, statements: list[CompanionStatement], meetings: list[CompanionMeeting]
) -> str:
    """M03 Task 5 (Entity Timeline) — mentions grouped by Meeting, sorted by
    Meeting.meeting_date (see models.CompanionMeeting's docstring: part of
    Contract v1.1's "Meeting" section, originally read ahead of any contract
    covering it, formalized once Companion published the addendum).

    This is a timeline of MENTIONS, not of field-level CHANGES to the object
    itself — Reader reads a single current snapshot of each object file, not
    Companion's git history, so it has no way to know what an object's fields
    looked like at an earlier point in time. Conflating "mentioned in a
    meeting on this date" with "the object's data changed on this date"
    would overstate what Reader can actually see; this function only claims
    the former."""
    by_meeting_id = {m.id: m for m in meetings}
    linked = linked_statements(obj.id, statements)
    counts: dict[str, int] = {}
    for s in linked:
        counts[s.meeting_ref] = counts.get(s.meeting_ref, 0) + 1

    entries = []
    for meeting_id, count in counts.items():
        meeting = by_meeting_id.get(meeting_id)
        date = meeting.meeting_date if meeting and meeting.meeting_date else None
        title = meeting.title if meeting else meeting_id
        entries.append((date, title, count))

    # Undated entries sort last, in a stable, deterministic (title) order —
    # never silently dropped just because Meeting.meeting_date is absent.
    entries.sort(key=lambda e: (e[0] is None, e[0] or "", e[1]))

    lines = []
    for date, title, count in entries:
        lines.append(date or "(date unknown)")
        lines.append("")
        lines.append(f"{count} mention(s) in {title}")
        lines.append("")
    return "\n".join(lines).rstrip("\n")
