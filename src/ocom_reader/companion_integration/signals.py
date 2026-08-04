"""Signal-based filtering and display — Reader M01 (filter, basic view) and
M02 (Meeting Summary, Signal Browser, full Signal View).

Per docs/contracts/companion-reader-contract.md: `detected_signals` is a set of
INDEPENDENTLY true signals, not an enumerable list of allowed combinations.
Every function in this module reasons about ONE signal name at a time. Do not
add a function that switches on a frozenset/tuple of multiple signals (e.g.
`if signals == {"metric", "task"}: ...`) — that is exactly the pattern the
contract prohibits, because the combination space is not closed and keeps
growing as Companion ingests more real transcripts (see the contract's own
evidence: 19 distinct combinations across just 5 transcripts in Companion's
M07 validation).

M02 note on `render_statement()`: its output format changed from M01's bare
Kind/Detected-Signals block to the fuller Signal View (separators, Speaker,
Text) requested for M02. This is a Reader-internal display change, not a
Contract change — companion-reader-contract.md governs Statement's *data*
fields, not how Reader chooses to print them. M01's own tests for the old
format were updated alongside this change (see tests/test_companion_integration.py).
"""

from __future__ import annotations

from ocom_reader.companion_integration.models import (
    KNOWN_SIGNALS,
    SIGNAL_DISPLAY_ORDER,
    CompanionStatement,
)

_SEPARATOR = "─" * 40


def filter_by_signal(statements: list[CompanionStatement], signal: str) -> list[CompanionStatement]:
    """All statements independently carrying `signal`, regardless of what else
    is in their detected_signals. A Statement whose detected_signals is
    ["task", "metric"] matches filter_by_signal(stmts, "task") AND
    filter_by_signal(stmts, "metric") separately — there is deliberately no
    way to ask this function for a specific combination."""
    if signal not in KNOWN_SIGNALS:
        raise ValueError(
            f"Unknown signal {signal!r} — must be one of {sorted(KNOWN_SIGNALS)}, "
            f"per companion-reader-contract.md's closed signal vocabulary."
        )
    return [s for s in statements if s.has_signal(signal)]


def signal_counts(statements: list[CompanionStatement]) -> dict[str, int]:
    """Count of Statements carrying each signal, computed independently per
    signal (never by combination) — the same discipline as filter_by_signal,
    just for all five signals at once."""
    return {sig: len(filter_by_signal(statements, sig)) for sig in SIGNAL_DISPLAY_ORDER}


def multi_signal_count(statements: list[CompanionStatement]) -> int:
    return sum(1 for s in statements if len(s.detected_signals) >= 2)


def zero_signal_count(statements: list[CompanionStatement]) -> int:
    return sum(1 for s in statements if not s.detected_signals)


def render_meeting_summary(statements: list[CompanionStatement]) -> str:
    """M02 Task 1 — the Meeting Summary block, for whatever Statements are
    passed in (typically: every Statement belonging to one Meeting)."""
    counts = signal_counts(statements)
    label_width = max(len(sig) for sig in SIGNAL_DISPLAY_ORDER) + 1  # +1 for ":"
    signal_lines = [
        f"{(sig.capitalize() + ':').ljust(label_width + 1)}{counts[sig]}"
        for sig in SIGNAL_DISPLAY_ORDER
    ]
    return "\n".join(
        [
            "Meeting Summary",
            "",
            f"Statements: {len(statements)}",
            "",
            "Signals",
            "",
            *signal_lines,
            "",
            f"Multi-signal: {multi_signal_count(statements)}",
            f"Zero-signal: {zero_signal_count(statements)}",
        ]
    )


def render_signal_browser(statements: list[CompanionStatement]) -> str:
    """M02 Task 2 — every Statement grouped by signal, in SIGNAL_DISPLAY_ORDER.
    A Statement carrying more than one signal appears once under EACH signal
    it carries — intentional, not a duplication bug: detected_signals is a
    set of independent facts about that Statement, and a browser grouped by
    signal has to show it wherever it's independently true. All five signal
    groups are always shown, even when empty, so the browser is a complete
    map of what's (and isn't) present, not just the non-empty subset."""
    blocks = []
    for sig in SIGNAL_DISPLAY_ORDER:
        matches = filter_by_signal(statements, sig)
        blocks.append(f"{sig.upper()} ({len(matches)})")
        blocks.append("")
        if matches:
            blocks.extend(s.id for s in matches)
        else:
            blocks.append("(none)")
        blocks.append("")
    return "\n".join(blocks).rstrip("\n")


def render_statement(stmt: CompanionStatement) -> str:
    """M02 Task 3 — the full Signal View: Speaker, Kind, Detected Signals (in
    SIGNAL_DISPLAY_ORDER, not raw storage order), and the full Text, framed
    by separators."""
    lines = [
        _SEPARATOR,
        "",
        "Statement",
        "",
        "Speaker:",
        stmt.speaker,
        "",
        "Kind:",
        stmt.statement_kind or "(none)",
        "",
        "Detected Signals",
        "",
    ]
    present = [sig for sig in SIGNAL_DISPLAY_ORDER if stmt.has_signal(sig)]
    if present:
        lines.extend(f"✓ {sig}" for sig in present)
    else:
        lines.append("(none)")
    lines += ["", "Text", "", stmt.text, "", _SEPARATOR]
    return "\n".join(lines)
