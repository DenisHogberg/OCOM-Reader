"""Web UI (M018) — the browser as another Reader client, not another
implementation. See docs/architecture/MILESTONE-018.md.
"""

from ocom_reader.web.server import DEFAULT_HOST, DEFAULT_PORT, start_server

__all__ = ["start_server", "DEFAULT_HOST", "DEFAULT_PORT"]
