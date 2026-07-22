"""Application configuration.

Plain pydantic model populated from environment variables. No config
framework — Phase 1 has exactly two knobs.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path("./data")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("OCOM_DATA_DIR", "./data")),
            log_level=os.environ.get("OCOM_LOG_LEVEL", "INFO"),
        )
