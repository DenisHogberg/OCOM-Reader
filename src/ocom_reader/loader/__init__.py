"""Repository Loader — reopen and change-detection primitives over
RepositoryIndex (M006). See docs/architecture/MILESTONE-011.md and
docs/architecture/MILESTONE-012.md (M012 revised this to read/diff-only;
persistence now lives in `persistence/`).
"""

from ocom_reader.loader.models import ChangeSet, FormatCompatibility
from ocom_reader.loader.repository_loader import RepositoryLoader

__all__ = [
    "RepositoryLoader",
    "ChangeSet",
    "FormatCompatibility",
]
