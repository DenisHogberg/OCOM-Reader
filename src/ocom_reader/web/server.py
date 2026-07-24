"""Web UI server — `ThreadingHTTPServer` (stdlib, threaded, so
concurrent requests are a real property, not an aspiration) plus a
hand-written router. No business logic: every `/api/*` route parses
its query string and calls exactly one `web/api.py` function.

Binds to 127.0.0.1 by default, never 0.0.0.0 — this project's first
network listener, and a local documentation tool has no reason to be
reachable from the local network by default. See MILESTONE-018-DESIGN.md.
"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from ocom_reader.web import api as web_api
from ocom_reader.workspace import WorkspaceManager

STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def make_handler(
    default_repo: Path,
    workspace_state_path: Optional[Path],
    use_persistence: bool,
    plugin_kwargs: dict,
) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
            pass  # suppress default per-request stderr logging

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if parsed.path.startswith("/api/"):
                    self._handle_api(parsed.path, query)
                else:
                    self._handle_static(parsed.path)
            except web_api.ApiError as exc:
                self._send_json({"error": str(exc)}, status=exc.status)
            except Exception as exc:  # one bad request must never crash the server
                self._send_json({"error": str(exc)}, status=500)

        def _handle_api(self, path: str, query: dict) -> None:
            workspace = WorkspaceManager(state_path=workspace_state_path)
            repo_name = query.get("repo")

            if path == "/api/health":
                self._send_json(web_api.get_health())
                return

            if path == "/api/workspace":
                self._send_json(web_api.get_workspace(workspace))
                return

            repo_path = web_api.resolve_repo_path(repo_name, default_repo, workspace)

            if path == "/api/plugins":
                self._send_json(web_api.get_plugins(repo_path, plugin_kwargs))
            elif path == "/api/ask":
                self._send_json(web_api.get_ask(repo_path, query.get("q", ""), use_persistence))
            elif path == "/api/search":
                self._send_json(web_api.get_search(repo_path, query.get("q", ""), use_persistence))
            elif path == "/api/related":
                self._send_json(web_api.get_related(repo_path, query.get("id", ""), use_persistence))
            elif path == "/api/explain":
                self._send_json(web_api.get_explain(repo_path, query.get("q", ""), use_persistence))
            else:
                self._send_json({"error": "Not found"}, status=404)

        def _handle_static(self, path: str) -> None:
            if path == "/":
                path = "/index.html"
            file_path = (STATIC_DIR / path.lstrip("/")).resolve()
            if not (file_path == STATIC_DIR or file_path.is_relative_to(STATIC_DIR)) or not file_path.is_file():
                self._send_json({"error": "Not found"}, status=404)
                return
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def start_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    repository_root: Path = Path("."),
    workspace_state_path: Optional[Path] = None,
    use_persistence: bool = True,
    plugin_state_path: Optional[Path] = None,
    plugin_dir: Optional[Path] = None,
) -> ThreadingHTTPServer:
    plugin_kwargs = {}
    if plugin_state_path is not None:
        plugin_kwargs["state_path"] = plugin_state_path
    if plugin_dir is not None:
        plugin_kwargs["user_plugin_dir"] = plugin_dir

    handler_cls = make_handler(Path(repository_root), workspace_state_path, use_persistence, plugin_kwargs)
    return ThreadingHTTPServer((host, port), handler_cls)
