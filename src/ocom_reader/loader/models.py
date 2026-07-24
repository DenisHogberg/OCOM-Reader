"""Loader data models.

`FormatCompatibility` moved to `persistence/models.py` in M012 (the
layer that actually owns stored versions); re-exported here so M011's
own public API (`from ocom_reader.loader import FormatCompatibility`)
keeps working unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ocom_reader.persistence.models import FormatCompatibility

__all__ = ["ChangeSet", "FormatCompatibility"]


class ChangeSet(BaseModel):
    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.removed)
