"""CLI — thin argparse wrapper over Reader. No logic of its own beyond
argument parsing and printing; every subcommand is one Reader call.

`search` and `related` print raw registry_ids (RetrievalMatch/RegistryEntry
are pointer-only — no title is resolved for them, the same way M007/M008
never resolved titles). `ask` and `explain` go through AnswerComposer,
the only place in this pipeline that resolves titles for presentation,
so their output is more readable. This asymmetry is deliberate, not an
oversight — see MILESTONE-009-010.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ocom_reader.composer.formatter import render
from ocom_reader.reader import Reader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocom-reader")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root to index (default: cwd)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Ask a question, get a composed answer")
    ask_parser.add_argument("query")

    search_parser = subparsers.add_parser("search", help="List ranked matching documents")
    search_parser.add_argument("query")

    related_parser = subparsers.add_parser("related", help="List documents directly related to a registry_id")
    related_parser.add_argument("registry_id")

    explain_parser = subparsers.add_parser("explain", help="Show found/related documents with reasons")
    explain_parser.add_argument("query")

    return parser


def _run_ask(reader: Reader, query: str) -> str:
    return render(reader.answer(query))


def _run_search(reader: Reader, query: str) -> str:
    matches = reader.search(query)
    if not matches:
        return f'No matches for "{query}".'
    lines = [f'Matches for "{query}":']
    lines.extend(f"  - {m.entry.registry_id} [score {m.score:g}]" for m in matches)
    return "\n".join(lines)


def _run_related(reader: Reader, registry_id: str) -> str:
    entries = reader.related(registry_id)
    if not entries:
        return f"No documents directly related to {registry_id}."
    lines = [f"Documents related to {registry_id}:"]
    lines.extend(f"  - {e.registry_id} ({e.entry_type})" for e in entries)
    return "\n".join(lines)


def _run_explain(reader: Reader, query: str) -> str:
    documents = reader.explain(query)
    if not documents:
        return f'Nothing found to explain for "{query}".'
    lines = [f'Explanation for "{query}":']
    for doc in documents:
        reasons = "; ".join(doc.reasons) if doc.reasons else "(no recorded reason)"
        lines.append(f"  - {doc.document.title} ({doc.document.path}): {reasons}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reader = Reader(args.repo)

    if args.command == "ask":
        output = _run_ask(reader, args.query)
    elif args.command == "search":
        output = _run_search(reader, args.query)
    elif args.command == "related":
        output = _run_related(reader, args.registry_id)
    elif args.command == "explain":
        output = _run_explain(reader, args.query)
    else:  # pragma: no cover — argparse enforces `required=True` over the choices above
        return 2

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
