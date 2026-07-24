"""Rich CLI output (M015) — pure formatting functions, no I/O beyond
the explicit `color`/`enabled` parameters each takes. `maybe_page` is
tested with `pydoc.pager` mocked, never invoking a real interactive
pager (which can hang — see MILESTONE-015.md for the reproduced bug
this discipline exists to prevent from ever reaching a test again).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ocom_reader import cli_output as co
from ocom_reader.composer.models import ComposedAnswer, DocumentRef, ExplainedDocument
from ocom_reader.registry.models import RegistryEntry
from ocom_reader.retrieval.models import MatchReason, RetrievalMatch


# --- supports_color -------------------------------------------------------


def test_supports_color_false_when_not_a_tty() -> None:
    with patch("sys.stdout.isatty", return_value=False):
        assert co.supports_color() is False


def test_supports_color_false_with_no_color_flag() -> None:
    with patch("sys.stdout.isatty", return_value=True):
        assert co.supports_color(no_color_flag=True) is False


def test_supports_color_false_with_no_color_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with patch("sys.stdout.isatty", return_value=True):
        assert co.supports_color() is False


def test_supports_color_true_when_tty_and_nothing_disables_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    with patch("sys.stdout.isatty", return_value=True):
        assert co.supports_color() is True


# --- style ------------------------------------------------------------------


def test_style_is_a_noop_when_color_is_false() -> None:
    assert co.style("text", "bold", color=False) == "text"


def test_style_wraps_in_ansi_codes_when_color_is_true() -> None:
    result = co.style("text", "bold", color=True)
    assert result.startswith("\033[1m")
    assert result.endswith("\033[0m")
    assert "text" in result


def test_style_on_empty_string_is_a_noop_even_with_color() -> None:
    assert co.style("", "bold", color=True) == ""


# --- render_markdown_inline --------------------------------------------------


def test_render_markdown_inline_strips_markers_when_color_is_false() -> None:
    result = co.render_markdown_inline("**bold** and *italic* and `code`", color=False)
    assert result == "bold and italic and code"


def test_render_markdown_inline_styles_bold_italic_and_code_when_color_is_true() -> None:
    result = co.render_markdown_inline("**bold** *italic* `code`", color=True)
    assert "\033[" in result
    assert "**" not in result
    assert "`" not in result


def test_render_markdown_inline_plain_text_is_unchanged() -> None:
    assert co.render_markdown_inline("just plain text", color=False) == "just plain text"
    assert co.render_markdown_inline("just plain text", color=True) == "just plain text"


# --- render_code_block / render_markdown -------------------------------------


def test_render_code_block_visually_distinguishes_a_fenced_block() -> None:
    text = "Intro.\n\n```python\ndef f():\n    return 1\n```\n\nOutro."
    result = co.render_code_block(text, color=False)
    assert "def f():" in result
    assert "  | " in result  # visual framing marker
    assert "Intro." in result
    assert "Outro." in result


def test_render_code_block_with_no_fence_is_unchanged() -> None:
    text = "Just a paragraph with no code."
    assert co.render_code_block(text, color=False) == text


def test_render_markdown_applies_code_block_before_inline_styling() -> None:
    text = "Before.\n\n```\nlet x = 1;\n```\n\nAfter with **bold**."
    result = co.render_markdown(text, color=False)
    assert "let x = 1;" in result
    assert "bold" in result
    assert "**" not in result


# --- render_table -----------------------------------------------------------


def test_render_table_empty_rows_is_empty_string() -> None:
    assert co.render_table(["a", "b"], [], color=False) == ""


def test_render_table_aligns_columns() -> None:
    result = co.render_table(["id", "score"], [["a", "1"], ["bb", "22"]], color=False)
    lines = result.splitlines()
    assert len(lines) == 4  # header + separator + 2 rows
    header_width = len(lines[0].split(" | ")[0])
    row_widths = {len(line.split(" | ")[0]) for line in lines[2:]}
    assert row_widths == {header_width}


def test_render_table_truncates_the_widest_column_to_respect_max_width() -> None:
    long_value = "x" * 200
    result = co.render_table(["id", "score"], [[long_value, "1"]], color=False, max_width=50)
    assert all(len(line) <= 55 for line in result.splitlines())  # small slack for separators
    assert "…" in result


def test_render_table_header_is_bold_when_color_is_true() -> None:
    result = co.render_table(["id"], [["a"]], color=True)
    assert "\033[1m" in result


# --- terminal size ------------------------------------------------------------


def test_terminal_width_and_height_return_positive_integers() -> None:
    assert co.terminal_width() > 0
    assert co.terminal_height() > 0


# --- maybe_page ---------------------------------------------------------------


def test_maybe_page_disabled_just_prints(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pydoc.pager") as mock_pager:
        co.maybe_page("short text", enabled=False)
        mock_pager.assert_not_called()
    assert "short text" in capsys.readouterr().out


def test_maybe_page_enabled_but_short_just_prints(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pydoc.pager") as mock_pager, patch.object(co, "terminal_height", return_value=100):
        co.maybe_page("short text", enabled=True)
        mock_pager.assert_not_called()
    assert "short text" in capsys.readouterr().out


def test_maybe_page_enabled_and_long_invokes_pager() -> None:
    long_text = "\n".join(f"line {i}" for i in range(50))
    with patch("pydoc.pager") as mock_pager, patch.object(co, "terminal_height", return_value=10):
        co.maybe_page(long_text, enabled=True)
        mock_pager.assert_called_once_with(long_text)


# --- Rich renderers: fixtures -------------------------------------------------


def _doc_ref(registry_id: str, title: str, preview: str = "") -> DocumentRef:
    return DocumentRef(
        registry_id=registry_id, document_id=registry_id, title=title, path=registry_id,
        document_type="ADR", preview=preview,
    )


def _explained(registry_id: str, title: str, reasons: list[str], score: float, preview: str = "") -> ExplainedDocument:
    return ExplainedDocument(document=_doc_ref(registry_id, title, preview), reasons=reasons, score=score)


# --- render_ask_rich ----------------------------------------------------------


def test_render_ask_rich_includes_all_four_sections() -> None:
    answer = ComposedAnswer(
        query="runtime",
        answer="Found 1 relevant document(s).",
        evidence=[_explained("a.md", "Runtime", ["Title match: runtime"], 10.0, preview="**Status:** Accepted")],
        related_documents=[],
        reading_order=[],
        grounded=True,
    )
    result = co.render_ask_rich(answer, color=False)
    assert "Question: runtime" in result
    assert "Answer" in result
    assert "Evidence" in result
    assert "Related Documents" in result
    assert "Recommended Reading Order" in result
    assert "Runtime" in result
    assert "Status: Accepted" in result  # markdown-rendered preview, ** stripped


def test_render_ask_rich_empty_sections_show_none_or_not_applicable() -> None:
    answer = ComposedAnswer(query="x", answer="No documentation found.", evidence=[], related_documents=[], reading_order=[], grounded=False)
    result = co.render_ask_rich(answer, color=False)
    assert "(none)" in result
    assert "(not applicable)" in result


def test_render_ask_rich_with_color_contains_ansi_codes() -> None:
    answer = ComposedAnswer(
        query="x", answer="Found.",
        evidence=[_explained("a.md", "A", ["Title match: x"], 10.0)],
        related_documents=[], reading_order=[], grounded=True,
    )
    result = co.render_ask_rich(answer, color=True)
    assert "\033[" in result


# --- render_search_rich --------------------------------------------------


def test_render_search_rich_no_matches() -> None:
    assert co.render_search_rich([], "nothing", color=False) == 'No matches for "nothing".'


def test_render_search_rich_renders_a_table() -> None:
    entry = RegistryEntry(registry_id="a.md", document_id="a.md", entry_type="ADR")
    matches = [RetrievalMatch(entry=entry, reasons=[MatchReason(kind="title_match", detail="x")], score=10.0)]
    result = co.render_search_rich(matches, "x", color=False)
    assert "a.md" in result
    assert "10" in result


# --- render_related_rich --------------------------------------------------


def test_render_related_rich_no_relations() -> None:
    assert co.render_related_rich([], "a.md", color=False) == "No documents directly related to a.md."


def test_render_related_rich_renders_a_table() -> None:
    entries = [RegistryEntry(registry_id="b.md", document_id="b.md", entry_type="Milestone")]
    result = co.render_related_rich(entries, "a.md", color=False)
    assert "b.md" in result
    assert "Milestone" in result


# --- render_explain_rich --------------------------------------------------


def test_render_explain_rich_nothing_found() -> None:
    assert co.render_explain_rich([], "x", color=False) == 'Nothing found to explain for "x".'


def test_render_explain_rich_lists_documents_with_reasons() -> None:
    documents = [_explained("a.md", "A", ["Title match: x"], 10.0)]
    result = co.render_explain_rich(documents, "x", color=False)
    assert "A" in result
    assert "Title match: x" in result


# --- Completion ---------------------------------------------------------------


def test_render_completion_script_bash() -> None:
    script = co.render_completion_script("bash")
    assert "_ocom_reader_completions" in script
    assert "ask search related explain completion" in script


def test_render_completion_script_unsupported_shell_raises() -> None:
    with pytest.raises(ValueError):
        co.render_completion_script("zsh")
