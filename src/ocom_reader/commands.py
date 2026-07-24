"""Command rendering — shared between one-shot CLI mode (cli.py) and
the interactive REPL (interactive.py), so both present a command the
exact same way. No logic of its own beyond formatting a Reader call's
result into a string; every function is one Reader call plus
presentation.
"""

from __future__ import annotations

from ocom_reader.composer.formatter import render
from ocom_reader.reader import Reader


def run_ask(reader: Reader, query: str) -> str:
    return render(reader.answer(query))


def run_search(reader: Reader, query: str) -> str:
    matches = reader.search(query)
    if not matches:
        return f'No matches for "{query}".'
    lines = [f'Matches for "{query}":']
    lines.extend(f"  - {m.entry.registry_id} [score {m.score:g}]" for m in matches)
    return "\n".join(lines)


def run_related(reader: Reader, registry_id: str) -> str:
    entries = reader.related(registry_id)
    if not entries:
        return f"No documents directly related to {registry_id}."
    lines = [f"Documents related to {registry_id}:"]
    lines.extend(f"  - {e.registry_id} ({e.entry_type})" for e in entries)
    return "\n".join(lines)


def run_explain(reader: Reader, query: str) -> str:
    documents = reader.explain(query)
    if not documents:
        return f'Nothing found to explain for "{query}".'
    lines = [f'Explanation for "{query}":']
    for doc in documents:
        reasons = "; ".join(doc.reasons) if doc.reasons else "(no recorded reason)"
        lines.append(f"  - {doc.document.title} ({doc.document.path}): {reasons}")
    return "\n".join(lines)
