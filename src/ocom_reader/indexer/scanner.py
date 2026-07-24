"""RepositoryScanner — discovers Markdown files under a root directory.

Deterministic: always returns paths in sorted order. Reads no file
content — that is DocumentLoader's job. Excludes the same
never-part-of-the-repo directories this project's own .gitignore
already excludes (.venv, __pycache__, .pytest_cache, data, .git) —
without this, scanning from the project root would also walk into
installed packages under .venv and index their README/CHANGELOG
files, which are not this repository's documentation.
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = (".md",)

EXCLUDED_DIRECTORIES = frozenset(
    {".venv", ".git", "__pycache__", ".pytest_cache", "data", "node_modules"}
)


class RepositoryScanner:
    def __init__(self, root: Path) -> None:
        self._root = root

    def scan(self) -> list[Path]:
        discovered: list[Path] = []
        for path in self._root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            relative_parts = path.relative_to(self._root).parts
            if any(part in EXCLUDED_DIRECTORIES or part.endswith(".egg-info") for part in relative_parts):
                continue
            discovered.append(path)
        return sorted(discovered)
