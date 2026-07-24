"""Migration scaffold.

Only `storage_version = 1` has ever existed, so `MIGRATIONS` starts
empty — there is nothing real to migrate from yet. The chaining
mechanism itself is exercised by a test that registers a synthetic
`0 -> 1` function against a hand-built legacy-shaped payload
(tests/test_persistence.py), the same "prove the mechanism before a
real case exists" discipline M011 used for format-incompatibility
recovery.
"""

from __future__ import annotations

from typing import Callable

from ocom_reader.persistence.models import MigrationError

CURRENT_STORAGE_VERSION = 1

MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def migrate_to_current(data: dict, from_version: int) -> dict:
    version = from_version
    while version < CURRENT_STORAGE_VERSION:
        migrate_fn = MIGRATIONS.get(version)
        if migrate_fn is None:
            raise MigrationError(
                f"No migration registered from storage_version {version} to {version + 1}."
            )
        data = migrate_fn(data)
        version += 1
    return data
