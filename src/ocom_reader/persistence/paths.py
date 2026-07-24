"""The `.ocom/` layout — pure path functions, no I/O."""

from __future__ import annotations

from pathlib import Path


def ocom_dir(repository_root: Path) -> Path:
    return Path(repository_root) / ".ocom"


def metadata_path(repository_root: Path) -> Path:
    return ocom_dir(repository_root) / "metadata.json"


def index_path(repository_root: Path) -> Path:
    return ocom_dir(repository_root) / "index.json"


def registry_path(repository_root: Path) -> Path:
    return ocom_dir(repository_root) / "registry.json"


def retrieval_path(repository_root: Path) -> Path:
    return ocom_dir(repository_root) / "retrieval.json"
