"""Workspace data models — pure bookkeeping, no retrieval concepts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkspaceEntry(BaseModel):
    name: str
    path: str
    added_at: datetime


class WorkspaceState(BaseModel):
    version: int = 1
    entries: list[WorkspaceEntry] = Field(default_factory=list)
    active: Optional[str] = None


class WorkspaceError(Exception):
    pass
