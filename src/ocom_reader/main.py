"""Entry point.

Phase 1 wires config, logging, and storage only. No adapter is
registered yet — reading OCOM documentation is deliberately out of
scope until this foundation is confirmed.
"""

from __future__ import annotations

from ocom_reader.config import Settings
from ocom_reader.logging_setup import configure_logging
from ocom_reader.storage import LocalJSONStorage


def main() -> None:
    settings = Settings.from_env()
    logger = configure_logging(settings.log_level)
    storage = LocalJSONStorage(settings.data_dir)

    object_count = sum(1 for _ in storage.list())
    logger.info(
        "OCOM Reader core initialized (data_dir=%s, stored_objects=%d)",
        settings.data_dir,
        object_count,
    )


if __name__ == "__main__":
    main()
