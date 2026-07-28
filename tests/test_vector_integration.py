"""Reader M01 (Contract Compliance) and M02 (Signal Explorer) —
docs/contracts/vector-reader-contract.md (published by Vector, Contract
Version 1.0) plus the summary/browser/query/stats layer M02 builds on top of it.

Four kinds of coverage: the models/loader/signals modules in isolation against
synthetic fixtures (old-style Statement with no detected_signals, new-style
with it, and an unknown extra field that must be ignored, not rejected); the
per-signal-not-combination discipline the contract requires, now also for
combinable signal:/speaker:/meeting: queries (M02 Task 5); one real
integration test reading Vector's own actual, already-ingested M07 validation
data directly from disk (not a copy) — both pre- and post-detected_signals
Statements genuinely exist there side by side; and M02's new summary/browser/
stats rendering, checked both structurally and against real data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ocom_reader.vector_integration.loader import (
    find_current_meetings,
    load_meetings,
    load_objects,
    load_statements,
    parse_frontmatter,
)
from ocom_reader.vector_integration.models import (
    SIGNAL_DISPLAY_ORDER,
    VectorMeeting,
    VectorObject,
    VectorStatement,
)
from ocom_reader.vector_integration.navigation import (
    filter_to_current_meetings,
    find_object,
    linked_meeting_ids,
    linked_statements,
    meetings_mentioning,
    mentions,
    render_cross_meeting_view,
    render_entity_timeline,
    render_mentions,
    render_object_view,
    render_relationship_tree,
)
from ocom_reader.vector_integration.promotion import (
    ALWAYS_SHOWN_GROUPS,
    UNCLASSIFIED,
    UNKNOWN_MEETING_LABEL,
    group_by_statement_kind,
    render_promotion_review,
)
from ocom_reader.vector_integration.query import apply_filters, parse_query
from ocom_reader.vector_integration.query import search as vector_search
from ocom_reader.vector_integration.signals import (
    filter_by_signal,
    multi_signal_count,
    render_meeting_summary,
    render_signal_browser,
    render_statement,
    signal_counts,
    zero_signal_count,
)
from ocom_reader.vector_integration.stats import compute_stats, render_stats

# Vector's own repository, read directly — not copied into this repo's fixtures.
# Reader M01 exists specifically to prove Reader can consume Vector's real output
# without either repository changing to accommodate the other.
VECTOR_REPO = Path("/Users/mac/Downloads/Vector")


def _write_statement(tmp_path: Path, name: str, extra_frontmatter: str = "") -> Path:
    # load_statements() only globs "STM-*.md" (mirroring Vector's own naming
    # convention, docs/identifiers-and-naming.md) — test filenames must match.
    if not name.startswith("STM-"):
        name = f"STM-{name}"
    path = tmp_path / name
    path.write_text(
        "---\n"
        "id: STM-20260101-TEST\n"
        "type: statement\n"
        "title: \"a test statement\"\n"
        "tenant: vector-primary\n"
        "owner: \"Unassigned\"\n"
        "status: Active\n"
        "lifecycle: none\n"
        "language: en\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "confidence: low\n"
        "source: ai\n"
        "speaker: \"Speaker 1\"\n"
        "meeting_ref: MTG-20260101-TEST\n"
        "timestamp: '00:01'\n"
        "text: \"we need to pay the vendor\"\n"
        f"{extra_frontmatter}"
        "---\n\n"
        "## Text\n\nwe need to pay the vendor\n",
        encoding="utf-8",
    )
    return path


def test_old_style_statement_without_detected_signals_still_loads(tmp_path: Path) -> None:
    """Task 1/2 — a Statement predating detected_signals must load safely, with
    an empty list, never None and never a crash."""
    _write_statement(tmp_path, "old.md")
    statements = load_statements(tmp_path)
    assert len(statements) == 1
    assert statements[0].detected_signals == []
    assert statements[0].has_signal("task") is False


def test_new_style_statement_with_detected_signals_loads(tmp_path: Path) -> None:
    _write_statement(
        tmp_path, "new.md",
        extra_frontmatter="detected_signals: [task, metric]\nstatement_kind: task_signal\n",
    )
    statements = load_statements(tmp_path)
    assert statements[0].detected_signals == ["task", "metric"]
    assert statements[0].has_signal("task") is True
    assert statements[0].has_signal("metric") is True
    assert statements[0].has_signal("risk") is False


def test_old_and_new_style_statements_load_together(tmp_path: Path) -> None:
    """Task 2 — backward compatibility means BOTH shapes work in the same run,
    not one or the other."""
    (tmp_path / "sub").mkdir()
    old_path = _write_statement(tmp_path, "old.md")
    new_path = _write_statement(tmp_path / "sub", "new.md", extra_frontmatter="detected_signals: [risk]\n")
    # Give the two files distinct ids so they don't collide as "the same" object.
    new_path.write_text(
        new_path.read_text().replace("id: STM-20260101-TEST", "id: STM-20260101-NEW2")
    )

    statements = load_statements(tmp_path)
    assert len(statements) == 2
    by_signals = {s.id: s.detected_signals for s in statements}
    assert by_signals["STM-20260101-TEST"] == []
    assert by_signals["STM-20260101-NEW2"] == ["risk"]


def test_unknown_field_is_ignored_not_rejected(tmp_path: Path) -> None:
    """The contract's core forward-compatibility promise: a field this version of
    Reader has never heard of must not cause a validation error."""
    path = _write_statement(
        tmp_path, "future.md",
        extra_frontmatter="some_future_field_vector_might_add: {nested: true}\n",
    )
    data = parse_frontmatter(path)
    assert data is not None
    stmt = VectorStatement.model_validate(data)  # must not raise
    assert not hasattr(stmt, "some_future_field_vector_might_add")


def test_non_statement_markdown_is_skipped_not_errored(tmp_path: Path) -> None:
    """README.md / REVIEW.md and any other non-Vector-object Markdown sitting
    alongside real Statements must never abort loading the real ones."""
    (tmp_path / "README.md").write_text("# Not a Vector object\n")
    _write_statement(tmp_path, "STM-real.md")
    statements = load_statements(tmp_path)
    assert len(statements) == 1


def test_filter_by_signal_is_independent_per_signal_not_by_combination(tmp_path: Path) -> None:
    """Task 5 — a Statement carrying {task, metric} must match a query for
    EITHER signal independently. This test would fail if filter_by_signal (or
    anything upstream) ever compared detected_signals as a fixed combination."""
    _write_statement(tmp_path, "multi.md", extra_frontmatter="detected_signals: [task, metric]\n")
    statements = load_statements(tmp_path)

    task_matches = filter_by_signal(statements, "task")
    metric_matches = filter_by_signal(statements, "metric")
    risk_matches = filter_by_signal(statements, "risk")

    assert len(task_matches) == 1
    assert len(metric_matches) == 1
    assert task_matches[0].id == metric_matches[0].id  # same Statement, two independent hits
    assert risk_matches == []


def test_filter_by_signal_rejects_unknown_signal_name(tmp_path: Path) -> None:
    _write_statement(tmp_path, "s.md")
    statements = load_statements(tmp_path)
    with pytest.raises(ValueError):
        filter_by_signal(statements, "not_a_real_signal")


def test_render_statement_full_signal_view(tmp_path: Path) -> None:
    """M02 Task 3 — the full Signal View: separators, Speaker, Kind, Detected
    Signals (in SIGNAL_DISPLAY_ORDER — task before metric, not alphabetical
    storage order), and Text. Supersedes M01's bare Kind/Detected-Signals
    block — a Reader-internal display change, not a Contract change."""
    _write_statement(
        tmp_path, "s.md",
        extra_frontmatter="detected_signals: [metric, task]\nstatement_kind: task_signal\n",
    )
    stmt = load_statements(tmp_path)[0]
    rendered = render_statement(stmt)
    assert rendered == "\n".join(
        [
            "─" * 40,
            "",
            "Statement",
            "",
            "Speaker:",
            "Speaker 1",
            "",
            "Kind:",
            "task_signal",
            "",
            "Detected Signals",
            "",
            "✓ task",
            "✓ metric",
            "",
            "Text",
            "",
            "we need to pay the vendor",
            "",
            "─" * 40,
        ]
    )


def test_render_statement_with_no_signals() -> None:
    stmt = VectorStatement.model_validate(
        {
            "id": "STM-1", "type": "statement", "title": "t", "tenant": "x", "owner": "o",
            "status": "Active", "lifecycle": "none", "language": "en", "created": "2026-01-01",
            "updated": "2026-01-01", "confidence": "low", "source": "ai",
            "speaker": "Speaker 1", "meeting_ref": "MTG-1", "timestamp": "00:01", "text": "hi",
        }
    )
    rendered = render_statement(stmt)
    assert "Kind:\n(none)" in rendered
    assert "Detected Signals\n\n(none)" in rendered
    assert rendered.startswith("─" * 40)
    assert rendered.endswith("─" * 40)


def test_find_current_meetings_excludes_superseded(tmp_path: Path) -> None:
    (tmp_path / "MTG-old.md").write_text(
        "---\nid: MTG-OLD\ntype: meeting\ntitle: t\nrelationships: []\n"
        "source_hash: 'sha256:abc'\nparser_version: '1.0.0'\n---\n\nbody\n"
    )
    (tmp_path / "MTG-new.md").write_text(
        "---\nid: MTG-NEW\ntype: meeting\ntitle: t\n"
        "relationships: [{type: supersedes, target: MTG-OLD}]\n"
        "source_hash: 'sha256:abc'\nparser_version: '1.4.0'\n---\n\nbody\n"
    )
    meetings = load_meetings(tmp_path)
    assert len(meetings) == 2
    current = find_current_meetings(meetings)
    assert [m.id for m in current] == ["MTG-NEW"]


# --- Real integration test: Vector's own actual M07 data, read live from disk ---

pytestmark_real_vector = pytest.mark.skipif(
    not VECTOR_REPO.exists(), reason="Vector repository not present at expected path"
)


@pytestmark_real_vector
def test_reads_all_real_vector_meetings_old_and_new_style() -> None:
    """Task 6 — compatibility check against real data: every Meeting/Statement
    Vector has actually produced across M01-M07, old-style (no
    detected_signals) and new-style (with it) side by side in the same
    staging directory tree, loads without error."""
    staging_root = VECTOR_REPO / "ai" / "staging"
    meetings = load_meetings(staging_root)
    statements = load_statements(staging_root)

    assert len(meetings) >= 10, "expected every real staged Meeting from M03-M07 runs"
    assert len(statements) > 500, "expected the full real Statement corpus across all runs"

    has_no_signals_field = [s for s in statements if s.detected_signals == []]
    has_signals_field = [s for s in statements if s.detected_signals]
    # Both old-style (pre-M04.3, or simply no signals detected) and populated
    # Statements coexist in Vector's real staging tree.
    assert has_signals_field, "expected at least some real Statements with detected_signals"
    assert has_no_signals_field, "expected at least some real Statements without any signal"


@pytestmark_real_vector
def test_reads_real_vector_production_objects() -> None:
    """Meetings/Statements are only ever in ai/staging/ in this repository so
    far (nothing has been promoted to objects/ yet) — but objects/ must still
    load cleanly (zero results, not an error) per the contract's tolerance for
    an empty or non-Vector-Statement tree."""
    objects_root = VECTOR_REPO / "objects"
    statements = load_statements(objects_root)  # must not raise
    assert statements == []


@pytestmark_real_vector
def test_signal_filter_against_real_data_matches_known_counts() -> None:
    """Cross-check against ai/pipelines/M06_RESULTS.md's own reported number for
    this exact Meeting (task_signal count 7, detected 'task' signal count 17,
    post-M06 parser_version 1.4.0) — proving Reader's independent
    reimplementation agrees with Vector's own analysis of the same file."""
    meeting_dir = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    if not meeting_dir.exists():
        pytest.skip("expected real M06/M07 staging run not present")
    statements = load_statements(meeting_dir)
    task_hits = filter_by_signal(statements, "task")
    assert len(task_hits) == 17


@pytestmark_real_vector
def test_find_current_meetings_against_real_supersedes_chain() -> None:
    """The real transcript was reprocessed multiple times across M03-M06
    (source_hash unchanged, parser_version bumped each time); exactly one
    Meeting in that chain must be current."""
    staging_root = VECTOR_REPO / "ai" / "staging"
    meetings = load_meetings(staging_root)
    same_source = [m for m in meetings if m.source_hash and m.source_hash.startswith(
        "sha256:700049850974"
    )]
    assert len(same_source) >= 5, "expected the known multi-reindex chain from M03-M06"
    current = find_current_meetings(same_source)
    assert len(current) == 1
    assert current[0].parser_version == "1.4.0"


# --- Reader M02 — Signal Explorer ------------------------------------------

def _stmt(
    id_, signals=(), speaker="Speaker 1", meeting_ref="MTG-X", text="hi", references=(),
    kind=None, timestamp="00:01",
) -> VectorStatement:
    return VectorStatement.model_validate(
        {
            "id": id_, "type": "statement", "title": text, "tenant": "x", "owner": "o",
            "status": "Active", "lifecycle": "none", "language": "en", "created": "2026-01-01",
            "updated": "2026-01-01", "confidence": "low", "source": "ai",
            "speaker": speaker, "meeting_ref": meeting_ref, "timestamp": timestamp, "text": text,
            "detected_signals": list(signals),
            "references": list(references),
            "statement_kind": kind,
        }
    )


def test_signal_counts_independent_per_signal() -> None:
    stmts = [_stmt("1", ["task"]), _stmt("2", ["task", "metric"]), _stmt("3", ["risk"]), _stmt("4", [])]
    counts = signal_counts(stmts)
    assert counts == {"task": 2, "metric": 1, "risk": 1, "decision": 0, "question": 0}


def test_multi_and_zero_signal_counts() -> None:
    stmts = [_stmt("1", ["task"]), _stmt("2", ["task", "metric"]), _stmt("3", [])]
    assert multi_signal_count(stmts) == 1
    assert zero_signal_count(stmts) == 1


def test_render_meeting_summary_task1_format() -> None:
    stmts = [
        _stmt("1", ["task"]), _stmt("2", ["task", "metric"]), _stmt("3", ["risk"]),
        _stmt("4", []), _stmt("5", []),
    ]
    rendered = render_meeting_summary(stmts)
    assert rendered.startswith("Meeting Summary\n\nStatements: 5\n\nSignals\n\n")
    assert "Task:" in rendered and "Metric:" in rendered and "Risk:" in rendered
    assert "Decision:" in rendered and "Question:" in rendered
    assert "Multi-signal: 1" in rendered
    assert "Zero-signal: 2" in rendered


def test_render_signal_browser_lists_all_five_groups_even_when_empty() -> None:
    stmts = [_stmt("STM-A", ["task"])]
    rendered = render_signal_browser(stmts)
    assert "TASK (1)" in rendered
    assert "STM-A" in rendered
    for sig in SIGNAL_DISPLAY_ORDER:
        assert f"{sig.upper()} (" in rendered  # every group present, even count 0


def test_render_signal_browser_multi_signal_statement_appears_under_each_group() -> None:
    """A Statement with two signals is not a duplication bug — it belongs
    under both groups, because both are independently true."""
    stmts = [_stmt("STM-MULTI", ["task", "risk"])]
    rendered = render_signal_browser(stmts)
    task_block = rendered.split("TASK (")[1].split("METRIC (")[0]
    risk_block = rendered.split("RISK (")[1].split("DECISION (")[0]
    assert "STM-MULTI" in task_block
    assert "STM-MULTI" in risk_block


def test_query_parse_and_apply_combines_filters() -> None:
    """M02 Task 4/5 — filters combine (AND), and signal: still goes through
    the same independent-per-signal check, never a combination.

    Note: the M02 query DSL splits on whitespace, so a filter value containing
    a space (e.g. a two-word speaker name) isn't representable as-is — a
    documented scope limit (see query.py's module docstring), exercised here
    with single-token speaker values instead."""
    stmts = [
        _stmt("1", ["task"], speaker="Denis", meeting_ref="MTG-AAA"),
        _stmt("2", ["task"], speaker="Angelina", meeting_ref="MTG-AAA"),
        _stmt("3", ["risk"], speaker="Denis", meeting_ref="MTG-AAA"),
    ]
    assert parse_query("signal:task speaker:Denis") == {"signal": "task", "speaker": "Denis"}

    only_signal = vector_search(stmts, "signal:task")
    assert {s.id for s in only_signal} == {"1", "2"}

    signal_and_speaker = vector_search(stmts, "signal:task speaker:Denis")
    assert {s.id for s in signal_and_speaker} == {"1"}  # narrower than either filter alone

    signal_and_meeting = apply_filters(stmts, {"signal": "task", "meeting": "AAA"})
    assert {s.id for s in signal_and_meeting} == {"1", "2"}


def test_query_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        parse_query("bogus:value")


def test_query_rejects_repeated_key() -> None:
    with pytest.raises(ValueError):
        parse_query("signal:task signal:risk")


def test_compute_and_render_stats() -> None:
    stmts = [_stmt("1", ["task"]), _stmt("2", ["metric", "risk"]), _stmt("3", [])]
    counts = signal_counts(stmts)
    stats = {"meetings": 2, "statements": len(stmts), **counts}
    rendered = render_stats(stats)
    assert rendered.startswith("Meetings\n\n2\n\nStatements\n\n3\n\n")
    assert "Tasks\n\n1" in rendered
    assert "Metrics\n\n1" in rendered
    assert "Risks\n\n1" in rendered
    assert "Decisions\n\n0" in rendered
    assert "Questions\n\n0" in rendered


@pytestmark_real_vector
def test_meeting_summary_against_real_data_matches_m06_numbers() -> None:
    """Cross-check against M06_RESULTS.md's own reported numbers for this
    exact Meeting post-M06 fixes (Zero-signal 43%, Multi-signal 23%)."""
    stmts = load_statements(VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL")
    assert zero_signal_count(stmts) == 42
    assert multi_signal_count(stmts) == 23


@pytestmark_real_vector
def test_stats_against_real_full_staging_tree() -> None:
    """Global stats over Vector's entire real ai/staging/ tree must not error
    and must report at least as many Statements as any single Meeting."""
    stats = compute_stats(VECTOR_REPO / "ai" / "staging")
    assert stats["meetings"] >= 10
    assert stats["statements"] > 500
    assert all(stats[sig] >= 0 for sig in SIGNAL_DISPLAY_ORDER)


@pytestmark_real_vector
def test_combined_query_against_real_data() -> None:
    """signal: + meeting: combined must narrow strictly to the intersection —
    fewer or equal results than either filter alone."""
    stmts = load_statements(VECTOR_REPO / "ai" / "staging")
    signal_only = filter_by_signal(stmts, "risk")
    combined = vector_search(stmts, "signal:risk meeting:XMFL")
    assert 0 < len(combined) <= len(signal_only)
    assert all(s.has_signal("risk") for s in combined)
    assert all("XMFL" in s.meeting_ref for s in combined)


# --- Reader M03 — Object Navigation -----------------------------------------
#
# Two kinds of coverage, for a reason documented in READER_M03.md: Vector's
# real objects (6 real Partner/Employee records) have zero populated
# `relationships` and zero `alias:` tags today (checked directly, not
# assumed) — so Aliases and the Relationship Browser are exercised here only
# against synthetic fixtures, while Linked Statements/Mentions/Cross-Meeting
# View/Timeline (which DO have real reference data behind them) are also
# checked against Vector's actual ai/staging/MTG-20260727-XMFL.

def _obj(
    id_, type_="partner", title="T", relationships=(), references=(), tags=(),
    evidence=(), source_type=None,
) -> VectorObject:
    return VectorObject.model_validate(
        {
            "id": id_, "type": type_, "title": title, "tenant": "x", "owner": "o",
            "status": "Active", "lifecycle": "commercial", "confidence": "low", "source": "ai",
            "relationships": list(relationships),
            "references": list(references),
            "tags": list(tags),
            "evidence": list(evidence),
            "source_type": source_type,
        }
    )


def test_find_object_by_id() -> None:
    objs = [_obj("PTN-1"), _obj("PTN-2")]
    assert find_object(objs, "PTN-2").id == "PTN-2"
    assert find_object(objs, "PTN-404") is None


def test_linked_statements_and_meeting_ids() -> None:
    stmts = [
        _stmt("1", meeting_ref="MTG-A", references=[{"target": "PTN-1"}]),
        _stmt("2", meeting_ref="MTG-A", references=[{"target": "PTN-1"}]),
        _stmt("3", meeting_ref="MTG-B", references=[{"target": "PTN-1"}]),
        _stmt("4", meeting_ref="MTG-A", references=[{"target": "PTN-2"}]),
    ]
    linked = linked_statements("PTN-1", stmts)
    assert {s.id for s in linked} == {"1", "2", "3"}
    assert linked_meeting_ids(linked) == ["MTG-A", "MTG-B"]


def test_render_object_view_with_aliases_and_relationships() -> None:
    """Task 1 — Object View. Uses a synthetic fixture for Aliases/
    Relationships since no real Vector object has either populated yet."""
    obj = _obj(
        "PTN-1", title="Angelina",
        relationships=[{"type": "works_with", "target": "CMP-1"}],
        tags=["alias:Ангеліна", "alias:Angie"],
    )
    stmts = [
        _stmt("1", meeting_ref="MTG-A", references=[{"target": "PTN-1"}]),
        _stmt("2", meeting_ref="MTG-B", references=[{"target": "PTN-1"}]),
    ]
    rendered = render_object_view(obj, stmts, [obj])
    assert "Type:\npartner" in rendered
    assert "Name:\nAngelina" in rendered
    assert "Linked Statements:\n2" in rendered
    assert "Meetings:\n2" in rendered
    assert "Ангеліна" in rendered and "Angie" in rendered
    assert "works_with → CMP-1" in rendered


def test_render_object_view_with_no_aliases_or_relationships() -> None:
    obj = _obj("PTN-2", title="Nobody")
    rendered = render_object_view(obj, [], [obj])
    assert "Linked Statements:\n0" in rendered
    assert "Meetings:\n0" in rendered
    assert "Aliases:\n(none)" in rendered
    assert "Relationships:\n(none)" in rendered
    assert "Evidence:\n(none)" in rendered


def test_render_object_view_with_evidence() -> None:
    """Reader M05 — Evidence view (Phase 3.1 PR-5, Option A: frontmatter-only,
    no Markdown body/excerpt parsing). Resolves obj.evidence ids against the
    objects list the exact same way mentions() resolves references — no new
    resolution mechanism."""
    evd = _obj("EVD-1", type_="evidence", title="Some excerpt", source_type="human_verification")
    obj = _obj("PTN-1", title="Angelina", evidence=["EVD-1"])
    rendered = render_object_view(obj, [], [obj, evd])
    assert "Evidence:\nhuman_verification — EVD-1" in rendered


def test_render_object_view_evidence_id_unresolved_is_skipped() -> None:
    """An evidence id not present among the loaded objects is skipped, not an
    error — same tolerance policy as mentions()'s unresolved references."""
    obj = _obj("PTN-1", title="Angelina", evidence=["EVD-GHOST"])
    rendered = render_object_view(obj, [], [obj])
    assert "Evidence:\n(none)" in rendered


def test_render_object_view_evidence_missing_source_type() -> None:
    """An Evidence object loaded without source_type (e.g. malformed data)
    renders an explicit placeholder rather than a blank or a crash."""
    evd = _obj("EVD-1", type_="evidence", title="Some excerpt")
    obj = _obj("PTN-1", title="Angelina", evidence=["EVD-1"])
    rendered = render_object_view(obj, [], [obj, evd])
    assert "Evidence:\n(source type unknown) — EVD-1" in rendered


def test_mentions_resolves_statement_references_to_objects() -> None:
    """Task 2 — Reverse Navigation: Statement -> mentions -> Object."""
    objs = [_obj("PTN-1", title="Angelina"), _obj("EMP-1", type_="employee", title="Oleh")]
    stmt = _stmt("1", references=[{"target": "PTN-1"}, {"target": "EMP-1"}])
    found = mentions(stmt, objs)
    assert [o.title for o in found] == ["Angelina", "Oleh"]
    assert "✓ Angelina" in render_mentions(stmt, objs)
    assert "✓ Oleh" in render_mentions(stmt, objs)


def test_mentions_skips_unresolvable_reference() -> None:
    """A reference target not present among the loaded objects is skipped,
    not an error — it may be genuinely unresolved, or simply not loaded from
    this particular root."""
    stmt = _stmt("1", references=[{"target": "PTN-GHOST"}])
    assert mentions(stmt, []) == []
    assert "(none)" in render_mentions(stmt, [])


def test_meetings_mentioning_and_cross_meeting_view() -> None:
    """Task 3 — Cross-Meeting View."""
    obj = _obj("PTN-1", title="Angelina")
    stmts = [
        _stmt("1", meeting_ref="MTG-A", references=[{"target": "PTN-1"}]),
        _stmt("2", meeting_ref="MTG-B", references=[{"target": "PTN-1"}]),
    ]
    meetings = [
        VectorMeeting.model_validate({"id": "MTG-A", "type": "meeting", "title": "Meeting A"}),
        VectorMeeting.model_validate({"id": "MTG-B", "type": "meeting", "title": "Meeting B"}),
    ]
    found = meetings_mentioning(obj, stmts, meetings)
    assert [m.title for m in found] == ["Meeting A", "Meeting B"]
    rendered = render_cross_meeting_view(obj, stmts, meetings)
    assert "Meeting A" in rendered and "Meeting B" in rendered


def test_render_relationship_tree_walks_typed_relationships() -> None:
    """Task 4 — Relationship Browser, a plain text tree (no graph library),
    generic over relationship type names — "works_with" here is just an
    example value, not something the walker hardcodes."""
    project = _obj("PRJ-1", type_="project", title="Roadmap")
    company = _obj(
        "CMP-1", type_="company", title="Acme", relationships=[{"type": "owns", "target": "PRJ-1"}]
    )
    person = _obj(
        "PTN-1", type_="partner", title="Angelina", relationships=[{"type": "works_with", "target": "CMP-1"}]
    )
    tree = render_relationship_tree(person, [person, company, project])
    assert tree.split("\n\n↓\n\n") == ["Partner", "works_with", "Company", "owns", "Project"]


def test_render_relationship_tree_handles_cycle_without_infinite_recursion() -> None:
    """A -> B -> A must terminate, not recurse forever. The closing back-
    reference to A is shown (so the cycle is visible in the tree) but is not
    itself expanded again — three "Partner" nodes total (A, B, back to A),
    not an unbounded repetition."""
    a = _obj("A", title="A", relationships=[{"type": "rel", "target": "B"}])
    b = _obj("B", title="B", relationships=[{"type": "rel", "target": "A"}])
    tree = render_relationship_tree(a, [a, b])
    assert tree.count("Partner") == 3
    assert tree.split("\n\n↓\n\n") == ["Partner", "rel", "Partner", "rel", "Partner"]


def test_render_relationship_tree_skips_unresolvable_target() -> None:
    a = _obj("A", title="A", relationships=[{"type": "rel", "target": "GHOST"}])
    tree = render_relationship_tree(a, [a])
    assert tree == "Partner"


def test_render_entity_timeline_sorts_by_meeting_date() -> None:
    """Task 5 — Entity Timeline. meeting_date is a Reader M03 addition beyond
    Contract v1.0 (see models.VectorMeeting docstring); undated meetings sort
    last rather than being dropped."""
    obj = _obj("PTN-1", title="Angelina")
    stmts = [
        _stmt("1", meeting_ref="MTG-LATE", references=[{"target": "PTN-1"}]),
        _stmt("2", meeting_ref="MTG-EARLY", references=[{"target": "PTN-1"}]),
        _stmt("3", meeting_ref="MTG-EARLY", references=[{"target": "PTN-1"}]),
        _stmt("4", meeting_ref="MTG-UNDATED", references=[{"target": "PTN-1"}]),
    ]
    meetings = [
        VectorMeeting.model_validate(
            {"id": "MTG-LATE", "type": "meeting", "title": "Late Meeting", "meeting_date": "2026-02-01"}
        ),
        VectorMeeting.model_validate(
            {"id": "MTG-EARLY", "type": "meeting", "title": "Early Meeting", "meeting_date": "2026-01-01"}
        ),
        VectorMeeting.model_validate(
            {"id": "MTG-UNDATED", "type": "meeting", "title": "Undated Meeting"}
        ),
    ]
    rendered = render_entity_timeline(obj, stmts, meetings)
    early_pos = rendered.index("Early Meeting")
    late_pos = rendered.index("Late Meeting")
    undated_pos = rendered.index("Undated Meeting")
    assert early_pos < late_pos < undated_pos
    assert "2 mention(s) in Early Meeting" in rendered
    assert "1 mention(s) in Late Meeting" in rendered
    assert "(date unknown)" in rendered


def test_filter_to_current_meetings_drops_superseded_reindex_runs() -> None:
    """Discovered against real data: the same real-world meeting reprocessed
    multiple times (Vector's own idempotent-import supersedes chain) must
    not be counted as several different meetings when aggregating a Statement
    count or a Cross-Meeting View / Timeline."""
    old_meeting = VectorMeeting.model_validate({"id": "MTG-OLD", "type": "meeting", "title": "T"})
    new_meeting = VectorMeeting.model_validate(
        {
            "id": "MTG-NEW", "type": "meeting", "title": "T",
            "relationships": [{"type": "supersedes", "target": "MTG-OLD"}],
        }
    )
    stmts = [
        _stmt("1", meeting_ref="MTG-OLD", references=[{"target": "PTN-1"}]),
        _stmt("2", meeting_ref="MTG-NEW", references=[{"target": "PTN-1"}]),
    ]
    filtered = filter_to_current_meetings(stmts, [old_meeting, new_meeting])
    assert [s.id for s in filtered] == ["2"]


@pytestmark_real_vector
def test_real_object_view_for_partner_angelina() -> None:
    """Cross-checks the two real references into PTN-20260727-A1NG confirmed
    directly (grep) in ai/staging/MTG-20260727-XMFL before writing this test."""
    root = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    objects = load_objects(VECTOR_REPO / "objects")
    obj = find_object(objects, "PTN-20260727-A1NG")
    assert obj is not None
    statements = load_statements(root)
    linked = linked_statements(obj.id, statements)
    assert len(linked) == 2
    assert linked_meeting_ids(linked) == ["MTG-20260727-XMFL"]
    # Real object: no relationships/aliases populated yet — an honest gap,
    # not a bug in this rendering.
    rendered = render_object_view(obj, statements, objects)
    assert "Aliases:\n(none)" in rendered
    assert "Relationships:\n(none)" in rendered
    # Phase 3.1 PR-2 populated real evidence: [EVD-20260728-6HFR] on this
    # object, with source_type: human_verification — confirmed directly
    # against objects/evidence/EVD-20260728-6HFR--angelina-owed-payment.md
    # before writing this assertion, not assumed.
    assert "Evidence:\nhuman_verification — EVD-20260728-6HFR" in rendered


@pytestmark_real_vector
def test_real_cross_meeting_view_for_employee_oleh() -> None:
    root = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    objects = load_objects(VECTOR_REPO / "objects")
    obj = find_object(objects, "EMP-20260727-O1EG")
    assert obj is not None
    statements = load_statements(root)
    meetings = load_meetings(root)
    found = meetings_mentioning(obj, statements, meetings)
    assert len(linked_statements(obj.id, statements)) == 5
    assert [m.id for m in found] == ["MTG-20260727-XMFL"]


@pytestmark_real_vector
def test_real_mentions_from_a_real_statement() -> None:
    """Reverse Navigation against a real Statement known (via grep) to
    reference PTN-20260727-A1NG."""
    root = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    objects = load_objects(VECTOR_REPO / "objects")
    statements = load_statements(root)
    referencing = [s for s in statements if any(r.get("target") == "PTN-20260727-A1NG" for r in s.references)]
    assert referencing, "expected at least one real Statement referencing PTN-20260727-A1NG"
    found = mentions(referencing[0], objects)
    assert any(o.id == "PTN-20260727-A1NG" for o in found)


@pytestmark_real_vector
def test_real_filter_to_current_meetings_collapses_reindex_chain() -> None:
    """The bug this filter fixes, reproduced against real data: loading the
    FULL ai/staging/ tree (not one scoped meeting directory) sees the same
    real meeting 6 times over (M03-M07's reindex chain, same source_hash).
    Without filtering, Angelina's Linked Statements/Meetings would be
    overcounted by that factor; with it, the real counts match the
    single-directory test above exactly (2 statements, 1 meeting)."""
    staging_root = VECTOR_REPO / "ai" / "staging"
    objects = load_objects(VECTOR_REPO / "objects")
    obj = find_object(objects, "PTN-20260727-A1NG")
    assert obj is not None
    meetings = load_meetings(staging_root)
    raw_statements = load_statements(staging_root)
    filtered = filter_to_current_meetings(raw_statements, meetings)
    linked = linked_statements(obj.id, filtered)
    assert len(linked) == 2
    assert linked_meeting_ids(linked) == ["MTG-20260727-XMFL"]


@pytestmark_real_vector
def test_real_entity_timeline_uses_real_meeting_date() -> None:
    """MTG-20260727-XMFL's real frontmatter does carry meeting_date (checked
    directly) — an exception among Vector's Meetings this milestone relies
    on, flagged in READER_M03.md."""
    root = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    objects = load_objects(VECTOR_REPO / "objects")
    obj = find_object(objects, "PTN-20260727-A1NG")
    assert obj is not None
    statements = load_statements(root)
    meetings = load_meetings(root)
    rendered = render_entity_timeline(obj, statements, meetings)
    assert "2026-07-27" in rendered
    assert "(date unknown)" not in rendered


# --- Reader M04 — Promotion Review UI ---------------------------------------
#
# Design Principle (READER_M04_DESIGN.md): Reader MUST NOT infer new semantic
# objects — grouping here is by the exact, literal statement_kind value only,
# never by a detected_signals combination. These tests check the grouping is
# a pure bucket-by-exact-value operation, that ordering (Meeting by
# meeting_date, Statement by timestamp) is deterministic even on ties, and
# that empty input never errors — the two points explicitly flagged for
# extra attention alongside the design.

def _meeting(id_, title="T", meeting_date=None) -> VectorMeeting:
    data = {"id": id_, "type": "meeting", "title": title}
    if meeting_date is not None:
        data["meeting_date"] = meeting_date
    return VectorMeeting.model_validate(data)


def test_group_by_statement_kind_buckets_by_exact_value() -> None:
    stmts = [
        _stmt("1", kind="task_signal"), _stmt("2", kind="task_signal"),
        _stmt("3", kind="risk_signal"), _stmt("4", kind=None),
    ]
    grouped = group_by_statement_kind(stmts)
    assert {s.id for s in grouped["task_signal"]} == {"1", "2"}
    assert {s.id for s in grouped["risk_signal"]} == {"3"}
    assert {s.id for s in grouped[UNCLASSIFIED]} == {"4"}
    assert "other" not in grouped  # never invented — only keys actually present


def test_group_by_statement_kind_keeps_unknown_future_value_separate() -> None:
    """A statement_kind value outside the 6 known ones (a hypothetical future
    Vector enum extension) must get its own bucket, never silently merged
    into 'other' or dropped."""
    stmts = [_stmt("1", kind="task_signal"), _stmt("2", kind="future_kind")]
    grouped = group_by_statement_kind(stmts)
    assert {s.id for s in grouped["future_kind"]} == {"2"}
    assert "other" not in grouped


def test_render_promotion_review_shows_all_seven_groups_even_when_empty() -> None:
    """The empty-results concern: no Statements of a given kind must still
    render a clear, explicit '(none)' — never an error, never a silently
    missing section."""
    rendered = render_promotion_review([], [])
    for key in ALWAYS_SHOWN_GROUPS:
        assert f"({0})" in rendered
    assert rendered.count("(none)") == len(ALWAYS_SHOWN_GROUPS)
    assert "TASK (0)" in rendered
    assert "UNCLASSIFIED (0)" in rendered


def test_render_promotion_review_completely_empty_input_never_errors() -> None:
    """Empty statements AND empty meetings — the fully-empty-repository case."""
    rendered = render_promotion_review([], [])
    assert rendered  # non-empty string, not a crash, not None


def test_render_promotion_review_groups_and_orders_by_meeting_date() -> None:
    meetings = [
        _meeting("MTG-LATE", title="Late Meeting", meeting_date="2026-02-01"),
        _meeting("MTG-EARLY", title="Early Meeting", meeting_date="2026-01-01"),
    ]
    stmts = [
        _stmt("1", kind="task_signal", meeting_ref="MTG-LATE", timestamp="00:01"),
        _stmt("2", kind="task_signal", meeting_ref="MTG-EARLY", timestamp="00:01"),
    ]
    rendered = render_promotion_review(stmts, meetings)
    assert rendered.index("Early Meeting") < rendered.index("Late Meeting")


def test_render_promotion_review_orders_statements_within_meeting_by_timestamp() -> None:
    meetings = [_meeting("MTG-A", title="Meeting A", meeting_date="2026-01-01")]
    stmts = [
        _stmt("LATER", kind="task_signal", meeting_ref="MTG-A", timestamp="00:10", text="later text"),
        _stmt("EARLIER", kind="task_signal", meeting_ref="MTG-A", timestamp="00:02", text="earlier text"),
    ]
    rendered = render_promotion_review(stmts, meetings)
    assert rendered.index("earlier text") < rendered.index("later text")


def test_render_promotion_review_undated_meeting_sorts_last() -> None:
    meetings = [
        _meeting("MTG-DATED", title="Dated Meeting", meeting_date="2026-01-01"),
        _meeting("MTG-UNDATED", title="Undated Meeting"),
    ]
    stmts = [
        _stmt("1", kind="risk_signal", meeting_ref="MTG-UNDATED"),
        _stmt("2", kind="risk_signal", meeting_ref="MTG-DATED"),
    ]
    rendered = render_promotion_review(stmts, meetings)
    assert rendered.index("Dated Meeting") < rendered.index("Undated Meeting")


def test_render_promotion_review_unresolvable_meeting_ref_goes_last_not_dropped() -> None:
    meetings = [_meeting("MTG-KNOWN", title="Known Meeting", meeting_date="2026-01-01")]
    stmts = [
        _stmt("1", kind="metric", meeting_ref="MTG-GHOST"),
        _stmt("2", kind="metric", meeting_ref="MTG-KNOWN"),
    ]
    rendered = render_promotion_review(stmts, meetings)
    assert UNKNOWN_MEETING_LABEL in rendered
    assert rendered.index("Known Meeting") < rendered.index(UNKNOWN_MEETING_LABEL)


def test_render_promotion_review_deterministic_tie_break_same_timestamp() -> None:
    """Stability concern: two Statements at the identical meeting_date AND
    timestamp must still render in a fixed, reproducible order across runs —
    tie-broken by Statement.id — not whatever order they happened to be
    passed in."""
    meetings = [_meeting("MTG-A", title="Meeting A", meeting_date="2026-01-01")]
    stmts_forward = [
        _stmt("STM-B", kind="task_signal", meeting_ref="MTG-A", timestamp="00:05", text="stmt b"),
        _stmt("STM-A", kind="task_signal", meeting_ref="MTG-A", timestamp="00:05", text="stmt a"),
    ]
    stmts_reversed = list(reversed(stmts_forward))
    rendered_forward = render_promotion_review(stmts_forward, meetings)
    rendered_reversed = render_promotion_review(stmts_reversed, meetings)
    assert rendered_forward == rendered_reversed
    # STM-A sorts before STM-B lexicographically — that's the deterministic tie-break.
    assert rendered_forward.index("stmt a") < rendered_forward.index("stmt b")


def test_render_promotion_review_malformed_timestamp_does_not_crash() -> None:
    meetings = [_meeting("MTG-A", title="Meeting A")]
    stmts = [_stmt("1", kind="task_signal", meeting_ref="MTG-A", timestamp="not-a-timestamp")]
    rendered = render_promotion_review(stmts, meetings)
    assert "TASK (1)" in rendered  # renders, doesn't raise


def test_render_promotion_review_unknown_kind_appended_after_known_groups() -> None:
    meetings = [_meeting("MTG-A", title="Meeting A", meeting_date="2026-01-01")]
    stmts = [_stmt("1", kind="future_kind", meeting_ref="MTG-A")]
    rendered = render_promotion_review(stmts, meetings)
    assert "FUTURE_KIND (1)" in rendered
    # Comes after all seven always-shown groups, not interleaved with them.
    assert rendered.index("OTHER (0)") < rendered.index("FUTURE_KIND (1)")


@pytestmark_real_vector
def test_real_promotion_review_task_signal_count_matches_known_number() -> None:
    """Cross-check against the same real, independently-confirmed number used
    in READER_M02.md and READER_M04_DESIGN.md: task_signal count 7 for this
    exact Meeting."""
    root = VECTOR_REPO / "ai" / "staging" / "MTG-20260727-XMFL"
    statements = load_statements(root)
    meetings = load_meetings(root)
    grouped = group_by_statement_kind(statements)
    assert len(grouped.get("task_signal", [])) == 7
    rendered = render_promotion_review(statements, meetings)
    assert "TASK (7)" in rendered


@pytestmark_real_vector
def test_real_promotion_review_against_full_repo_has_no_duplicate_meeting_sections() -> None:
    """The exact bug class M03 found (a real meeting reprocessed 6 times
    appearing as 6 duplicate sections) must not reappear here — this is why
    filter_to_current_meetings is a REQUIRED step, not optional, per
    READER_M04_DESIGN.md."""
    staging_root = VECTOR_REPO / "ai" / "staging"
    meetings = load_meetings(staging_root)
    statements = filter_to_current_meetings(load_statements(staging_root), meetings)
    rendered = render_promotion_review(statements, meetings)
    # This real Meeting has Statements of 5 different statement_kind values
    # (confirmed: task_signal, fact, metric, risk_signal, other all present),
    # so its title legitimately appears once PER group it has representatives
    # in, across a multi-meeting corpus where OTHER real meetings also
    # contribute to each group's total count. The bug this guards against is
    # the title appearing MORE than once WITHIN a single group's block (one
    # per stale reindex run of the same real meeting) — checked per-block
    # below, not as a single whole-document count (which this real, growing,
    # multi-meeting corpus makes the wrong thing to assert on).
    title = "Проєктні затримки та фінансові питання"
    group_prefixes = ["TASK (", "DECISION (", "RISK (", "METRIC (", "FACT (", "OTHER (", "UNCLASSIFIED ("]
    block_starts = sorted(rendered.index(p) for p in group_prefixes if p in rendered)
    assert len(block_starts) == len(group_prefixes), "expected all seven always-shown groups present"
    checked_at_least_one_block = False
    for i, start in enumerate(block_starts):
        end = block_starts[i + 1] if i + 1 < len(block_starts) else len(rendered)
        block = rendered[start:end]
        count = block.count(title)
        if count:
            checked_at_least_one_block = True
        assert count <= 1, f"block starting at {rendered[start:start+20]!r} shows this Meeting more than once"
    assert checked_at_least_one_block, "expected this Meeting to appear in at least one group's block"
