"""MarkdownParser — deterministic, regex-based extraction only.

No semantic interpretation, no Markdown-rendering library: headings,
links, and a preview snippet are pulled out by fixed, mechanical
rules, matching this milestone's explicit non-goal ("no semantic
interpretation yet") and this project's standing discipline of not
adding a dependency where a fixed rule already suffices.

`builds_on_links` (added for MILESTONE-007's Knowledge Registry):
every link found specifically on this project's own `**Builds on:**`
header line — a structural convention already present, unchanged,
in every document under docs/architecture/. This is the one addition
Knowledge Registry required here rather than re-parsing Markdown
itself: Repository Index stays the sole source of document data, and
this is a narrow extension of MarkdownParser's existing
link-extraction responsibility, not a new one. See
docs/architecture/MILESTONE-007.md for the justification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ocom_reader.indexer.models import Heading

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
BUILDS_ON_LINE_PATTERN = re.compile(r"^\*\*Builds on:\*\*(.*)$", re.MULTILINE)
PREVIEW_LENGTH = 240


@dataclass
class ParsedMarkdown:
    title: str
    headings: list[Heading] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    builds_on_links: list[str] = field(default_factory=list)
    preview: str = ""


class MarkdownParser:
    def parse(self, content: str, fallback_title: str) -> ParsedMarkdown:
        headings = [
            Heading(level=len(match.group(1)), text=match.group(2).strip())
            for match in HEADING_PATTERN.finditer(content)
        ]
        title = headings[0].text if headings else fallback_title
        links = [match.group(2).strip() for match in LINK_PATTERN.finditer(content)]
        builds_on_links = self._builds_on_links(content)
        preview = self._preview(content)

        return ParsedMarkdown(
            title=title,
            headings=headings,
            links=links,
            builds_on_links=builds_on_links,
            preview=preview,
        )

    def _builds_on_links(self, content: str) -> list[str]:
        match = BUILDS_ON_LINE_PATTERN.search(content)
        if not match:
            return []
        return [link.group(2).strip() for link in LINK_PATTERN.finditer(match.group(1))]

    def _preview(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            return stripped[:PREVIEW_LENGTH]
        return ""
