"""Persistence data models.

`FormatCompatibility` is the same shape M011 defined in `loader/models.py`
— redefined here as the one canonical copy (persistence is the layer
that actually knows about stored versions), with `loader/` re-exporting
it for backward compatibility with M011's own public API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StorageMetadata(BaseModel):
    storage_version: int
    reader_version: str
    repository_root: str
    created_at: datetime
    last_updated: datetime


class FormatCompatibility(BaseModel):
    compatible: bool
    stored_version: Optional[int]
    current_version: int
    reason: str


class MigrationError(Exception):
    pass
