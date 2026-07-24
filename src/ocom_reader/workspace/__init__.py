"""Multi-Repository Workspace — a name-to-path registry and active-repository
pointer, layered strictly above Reader. See docs/architecture/MILESTONE-016.md.
"""

from ocom_reader.workspace.models import WorkspaceEntry, WorkspaceError, WorkspaceState
from ocom_reader.workspace.workspace_manager import WorkspaceManager, default_workspace_path

__all__ = [
    "WorkspaceManager",
    "WorkspaceEntry",
    "WorkspaceState",
    "WorkspaceError",
    "default_workspace_path",
]
