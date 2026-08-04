"""Combinable `key:value` query filters for Reader M02's Signal Search —
`signal:task speaker:Denis meeting:XMFL`, any subset, in any order, all ANDed
together.

Scope, explicit and narrow for M02: each key may appear at most once per query.
Combining multiple *different* keys is fully supported (that's the actual
requirement); combining multiple *values for the same key* (e.g. two
`signal:` clauses meaning OR) is not — a repeated key raises rather than
silently discarding one of them, since silently dropping a filter the user
typed is worse than telling them plainly. If OR-within-a-key turns out to be
needed, that is a deliberate scope decision for a later milestone, not
something to guess at here.

`signal:` still goes through signals.filter_by_signal() — a single
independent signal name, never a combination — consistent with M01's
constraint, which this module does not relax.
"""

from __future__ import annotations

from ocom_reader.companion_integration.models import CompanionStatement
from ocom_reader.companion_integration.signals import filter_by_signal

KNOWN_FILTER_KEYS = frozenset({"signal", "speaker", "meeting"})


def parse_query(query: str) -> dict[str, str]:
    """Parse `"signal:task speaker:Denis"` into {"signal": "task", "speaker": "Denis"}."""
    filters: dict[str, str] = {}
    for token in query.split():
        if ":" not in token:
            raise ValueError(f"Invalid filter {token!r} — expected key:value")
        key, _, value = token.partition(":")
        if key not in KNOWN_FILTER_KEYS:
            raise ValueError(
                f"Unknown filter key {key!r} — expected one of {sorted(KNOWN_FILTER_KEYS)}"
            )
        if not value:
            raise ValueError(f"Filter {key!r} has no value")
        if key in filters:
            raise ValueError(
                f"Filter key {key!r} given more than once — M02 supports one value per "
                f"key per query (see query.py's module docstring)"
            )
        filters[key] = value
    return filters


def apply_filters(statements: list[CompanionStatement], filters: dict[str, str]) -> list[CompanionStatement]:
    """Apply every filter in `filters`, ANDed together — each filter narrows
    the previous result, in a fixed, deterministic order (signal, then
    speaker, then meeting) so results are reproducible regardless of the
    order keys happened to appear in the original query string."""
    result = statements
    if "signal" in filters:
        result = filter_by_signal(result, filters["signal"])
    if "speaker" in filters:
        needle = filters["speaker"].lower()
        result = [s for s in result if needle in s.speaker.lower()]
    if "meeting" in filters:
        needle = filters["meeting"].lower()
        result = [s for s in result if needle in s.meeting_ref.lower()]
    return result


def search(statements: list[CompanionStatement], query: str) -> list[CompanionStatement]:
    """Parse and apply a query string in one step — the function CLI's
    `companion search` calls."""
    return apply_filters(statements, parse_query(query))
