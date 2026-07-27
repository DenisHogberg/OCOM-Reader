"""Loads Vector Statement/Meeting objects from a Vector repository directory
(works against both `objects/` — production — and `ai/staging/<meeting-id>/` —
staged candidates; Reader treats them identically, since the contract makes no
distinction between the two for reading purposes).

Read-only. Never writes back into a Vector repository — Reader has no role in
Vector's write-back governance (Vector's own docs/ai-collaboration.md).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from ocom_reader.vector_integration.models import (
    KNOWN_OBJECT_TYPES,
    VectorMeeting,
    VectorObject,
    VectorStatement,
)

_NON_OBJECT_FILENAMES = {"README.md", "REVIEW.md"}

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(path: Path) -> Optional[dict]:
    """Split a Vector object's YAML frontmatter out of its Markdown body.
    Returns None (not an error) for any file that isn't frontmatter-shaped —
    Reader must tolerate non-Vector Markdown files sitting alongside real
    Vector objects (README.md, REVIEW.md are never Vector objects themselves,
    per Vector's own repository-rules.md naming convention)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def load_statements(root: Path) -> list[VectorStatement]:
    """Every valid Statement found anywhere under `root` (recursive — works
    against objects/statements/ and ai/staging/<meeting-id>/ alike). Silently
    skips anything that isn't a Statement or fails validation against the
    contract's mandatory fields — one malformed or unrelated file must never
    abort loading everything else."""
    statements = []
    for path in sorted(root.rglob("STM-*.md")):
        data = parse_frontmatter(path)
        if not data or data.get("type") != "statement":
            continue
        try:
            statements.append(VectorStatement.model_validate(data))
        except ValidationError:
            continue
    return statements


def load_meetings(root: Path) -> list[VectorMeeting]:
    """Every valid Meeting found anywhere under `root`. Same tolerance policy
    as load_statements()."""
    meetings = []
    for path in sorted(root.rglob("MTG-*.md")):
        data = parse_frontmatter(path)
        if not data or data.get("type") != "meeting":
            continue
        try:
            meetings.append(VectorMeeting.model_validate(data))
        except ValidationError:
            continue
    return meetings


def load_objects(root: Path) -> list[VectorObject]:
    """Every valid non-Statement/Meeting object found anywhere under `root`
    (Partner, Company, Employee, Task, Decision, Risk, Issue, Document,
    Project, Product, Evidence) — Reader M03's Object Navigation.

    Globs every `*.md` (not a type-specific filename prefix, since there is
    no single one across 11 different object types) and checks the `type`
    field against KNOWN_OBJECT_TYPES — the same authoritative-field-not-
    filename discipline load_statements()/load_meetings() already use.
    Statement and Meeting files are correctly excluded here (their `type` is
    "statement"/"meeting", not in KNOWN_OBJECT_TYPES) — use load_statements/
    load_meetings for those."""
    objects = []
    for path in sorted(root.rglob("*.md")):
        if path.name in _NON_OBJECT_FILENAMES:
            continue
        data = parse_frontmatter(path)
        if not data or data.get("type") not in KNOWN_OBJECT_TYPES:
            continue
        try:
            objects.append(VectorObject.model_validate(data))
        except ValidationError:
            continue
    return objects


def find_current_meetings(meetings: list[VectorMeeting]) -> list[VectorMeeting]:
    """Meetings not superseded by any other — the same algorithm Vector's own
    M03 pipeline uses to find the head of a source's reprocessing chain
    (ingest_transcript.find_existing_import), independently reimplemented here
    on Reader's side of the contract, read-only, from the same `supersedes`
    relationship data."""
    superseded_ids = {target for m in meetings for target in m.supersedes()}
    return [m for m in meetings if m.id not in superseded_ids]
