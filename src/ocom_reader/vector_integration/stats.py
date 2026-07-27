"""Reader M02 — `ocom-reader vector stats`: global counts across every Meeting
and Statement found under a Vector repository path.

Reports all five signals from SIGNAL_DISPLAY_ORDER, including `decision` —
the requested example output happened to omit a Decisions line, but Decision
is one of the contract's five known signals (models.KNOWN_SIGNALS) on equal
footing with the other four; silently dropping it from a "statistics" view
would hide real data for no stated reason, so it's included here.
"""

from __future__ import annotations

from pathlib import Path

from ocom_reader.vector_integration.loader import load_meetings, load_statements
from ocom_reader.vector_integration.models import SIGNAL_DISPLAY_ORDER
from ocom_reader.vector_integration.signals import signal_counts

_SIGNAL_LABELS = {
    "task": "Tasks",
    "metric": "Metrics",
    "risk": "Risks",
    "decision": "Decisions",
    "question": "Questions",
}


def compute_stats(root: Path) -> dict[str, int]:
    meetings = load_meetings(root)
    statements = load_statements(root)
    counts = signal_counts(statements)
    result = {"meetings": len(meetings), "statements": len(statements)}
    result.update(counts)
    return result


def render_stats(stats: dict[str, int]) -> str:
    lines = ["Meetings", "", str(stats["meetings"]), "", "Statements", "", str(stats["statements"])]
    for sig in SIGNAL_DISPLAY_ORDER:
        lines += ["", _SIGNAL_LABELS[sig], "", str(stats[sig])]
    return "\n".join(lines)
