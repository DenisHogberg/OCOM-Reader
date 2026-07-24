"""Rich CLI presentation (M015) — pure formatting, no Reader/Retrieval/
Registry/Indexer logic. Every function takes an explicit `color: bool`
rather than checking `sys.stdout.isatty()` itself, so every function
stays directly testable — the same "inject the decision" pattern
`interactive.py`'s `read_line`/`write` established in M013.

No new dependencies: raw ANSI escapes for color, hand-rolled column
alignment for tables, stdlib `pydoc.pager()` for paging. See
MILESTONE-015-DESIGN.md for why a real syntax highlighter and dynamic
shell completion were both deliberately scoped out rather than adding
this project's first third-party dependency.
"""

from __future__ import annotations

import os
import pydoc
import re
import shutil
import sys

from ocom_reader.composer.models import ComposedAnswer, ExplainedDocument
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.retrieval.models import RetrievalMatch

RESET = "\033[0m"
CODES = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "green": "\033[32m",
}

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_CODE_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n?(.*?)```", re.DOTALL)


def supports_color(no_color_flag: bool = False) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def style(text: str, *codes: str, color: bool) -> str:
    if not color or not text:
        return text
    prefix = "".join(CODES[c] for c in codes)
    return f"{prefix}{text}{RESET}"


def render_markdown_inline(text: str, color: bool) -> str:
    if not color:
        return _BOLD_RE.sub(r"\1", _ITALIC_RE.sub(r"\1", _CODE_SPAN_RE.sub(r"\1", text)))

    def _code(m: "re.Match[str]") -> str:
        return style(m.group(1), "cyan", color=color)

    def _bold(m: "re.Match[str]") -> str:
        return style(m.group(1), "bold", color=color)

    def _italic(m: "re.Match[str]") -> str:
        return style(m.group(1), "dim", color=color)

    text = _CODE_SPAN_RE.sub(_code, text)
    text = _BOLD_RE.sub(_bold, text)
    text = _ITALIC_RE.sub(_italic, text)
    return text


def render_code_block(text: str, color: bool) -> str:
    """Visually distinguishes fenced code blocks — dim/boxed framing,
    not per-language token coloring (see MILESTONE-015-DESIGN.md)."""

    def _block(m: "re.Match[str]") -> str:
        body = m.group(1).strip("\n")
        lines = [f"  | {line}" for line in body.splitlines()] or ["  | "]
        block_text = "\n".join(lines)
        return style(block_text, "dim", color=color) if color else block_text

    return _CODE_FENCE_RE.sub(_block, text)


def render_markdown(text: str, color: bool) -> str:
    """Full pass: code blocks first (so their contents aren't
    mistaken for inline bold/italic/code spans), then inline styling."""
    text = render_code_block(text, color)
    return render_markdown_inline(text, color)


def render_table(headers: list[str], rows: list[list[str]], color: bool, max_width: int = 100) -> str:
    if not rows:
        return ""

    columns = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i in range(columns):
            widths[i] = max(widths[i], len(str(row[i])))

    total = sum(widths) + 3 * (columns - 1)
    if total > max_width and columns > 0:
        overflow = total - max_width
        widest = widths.index(max(widths))
        widths[widest] = max(10, widths[widest] - overflow)

    def _fit(value: str, width: int) -> str:
        if len(value) <= width:
            return value.ljust(width)
        return (value[: width - 1] + "…").ljust(width)

    lines = []
    header_line = " | ".join(_fit(h, w) for h, w in zip(headers, widths))
    lines.append(style(header_line, "bold", color=color))
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        lines.append(" | ".join(_fit(str(cell), w) for cell, w in zip(row, widths)))
    return "\n".join(lines)


def terminal_width(default: int = 100) -> int:
    return shutil.get_terminal_size((default, 24)).columns


def terminal_height(default: int = 24) -> int:
    return shutil.get_terminal_size((100, default)).lines


def maybe_page(text: str, enabled: bool) -> None:
    if enabled and text.count("\n") + 1 > terminal_height():
        pydoc.pager(text)
    else:
        print(text)


def _render_document_block(doc: ExplainedDocument, color: bool) -> str:
    title = style(doc.document.title, "bold", color=color)
    lines = [f"  - {title} ({doc.document.path}) [score {doc.score:g}]"]
    if doc.reasons:
        lines.append(f"      {'; '.join(doc.reasons)}")
    if doc.document.preview:
        preview = render_markdown(doc.document.preview, color)
        lines.append(f"      {style('Preview:', 'dim', color=color)} {preview}")
    return "\n".join(lines)


def render_ask_rich(answer: ComposedAnswer, color: bool) -> str:
    lines = [style(f"Question: {answer.query}", "bold", color=color), ""]

    lines.append(style("Answer", "bold", "cyan", color=color))
    lines.append(f"  {answer.answer}")
    lines.append("")

    lines.append(style("Evidence", "bold", "cyan", color=color))
    if answer.evidence:
        lines.extend(_render_document_block(doc, color) for doc in answer.evidence)
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(style("Related Documents", "bold", "cyan", color=color))
    if answer.related_documents:
        lines.extend(_render_document_block(doc, color) for doc in answer.related_documents)
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(style("Recommended Reading Order", "bold", "cyan", color=color))
    if answer.reading_order:
        for i, doc in enumerate(answer.reading_order, start=1):
            lines.append(f"  {i}. {style(doc.title, 'bold', color=color)} ({doc.path})")
    else:
        lines.append("  (not applicable)")

    return "\n".join(lines)


def render_search_rich(matches: list[RetrievalMatch], query: str, color: bool) -> str:
    if not matches:
        return f'No matches for "{query}".'
    header = style(f'Matches for "{query}":', "bold", color=color)
    rows = [[str(i), m.entry.registry_id, f"{m.score:g}"] for i, m in enumerate(matches, start=1)]
    table = render_table(["#", "registry_id", "score"], rows, color=color, max_width=terminal_width())
    return f"{header}\n{table}"


def render_related_rich(entries: list[RegistryEntry], registry_id: str, color: bool) -> str:
    if not entries:
        return f"No documents directly related to {registry_id}."
    header = style(f"Documents related to {registry_id}:", "bold", color=color)
    rows = [[str(i), e.registry_id, e.entry_type] for i, e in enumerate(entries, start=1)]
    table = render_table(["#", "registry_id", "type"], rows, color=color, max_width=terminal_width())
    return f"{header}\n{table}"


def render_explain_rich(documents: list[ExplainedDocument], query: str, color: bool) -> str:
    if not documents:
        return f'Nothing found to explain for "{query}".'
    lines = [style(f'Explanation for "{query}":', "bold", color=color)]
    lines.extend(_render_document_block(doc, color) for doc in documents)
    return "\n".join(lines)


BASH_COMPLETION = """\
_ocom_reader_completions() {
    local cur commands flags
    cur="${COMP_WORDS[COMP_CWORD]}"
    commands="ask search related explain completion"
    flags="--repo --no-cache --plain --help"
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
    elif [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
    fi
}
complete -F _ocom_reader_completions ocom-reader
"""


def render_completion_script(shell: str) -> str:
    if shell == "bash":
        return BASH_COMPLETION
    raise ValueError(f"Unsupported shell: {shell!r}. Supported: bash.")
