# MILESTONE-018: Web UI — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation.
**Builds on:** [MILESTONE-017](MILESTONE-017.md), [MILESTONE-016](MILESTONE-016.md)

## Objective

The browser is another client of `Reader` — not another implementation.
No browser-facing code performs retrieval, ranking, persistence,
repository indexing, or plugin loading; every one of those still goes
through the exact same `Reader`/`WorkspaceManager`/`PluginManager`
calls the CLI already uses.

## Two Decisions Worth Flagging Explicitly

### 1. Tech stack: stdlib only, zero new dependencies

`pyproject.toml` has depended on `pydantic` alone since Phase 1. Every
prior milestone that could have reached for a library instead built a
small stdlib-based equivalent (M015's hand-rolled tables instead of
`rich`, `pydoc.pager` instead of a paging library, raw ANSI instead of
`colorama`). Continuing that discipline here:

- **Backend**: `http.server.ThreadingHTTPServer` (stdlib, threaded —
  directly satisfies "concurrent requests" without a third-party ASGI/WSGI
  server) plus a hand-written request handler routing to a small JSON API.
  Not Flask/FastAPI — a real, deliberate choice, not an oversight.
- **Frontend**: static HTML/CSS/vanilla JavaScript (`fetch()` for the
  API calls), no build step, no npm/node, no React/Vue. Served as
  static files from the same process.

### 2. Binds to `127.0.0.1` only, never `0.0.0.0`

This is the project's first-ever network listener. Defaulting to
loopback-only is a real security decision, not an afterthought — a
local documentation tool has no reason to be reachable from the local
network by default. `--host` is exposed for someone who explicitly
wants otherwise, but the default is loopback.

## Architecture

```
Browser (static HTML/CSS/JS)
        ↓ fetch()
Web UI internal API (web/api.py)
        ↓
Reader / WorkspaceManager / PluginManager  (unchanged, M009-010/M016/M017)
        ↓
Composer → Retrieval → Registry → Index   (unchanged)
```

`web/api.py` is the *only* new code that touches `Reader`, and every
one of its functions is a thin wrapper: resolve a repository path
(same `WorkspaceManager.resolve()` logic `cli.py` already uses),
construct a `Reader`, call one existing method, serialize the result
with `.model_dump(mode="json")`. No new matching, ranking, or
composition logic — mirroring `commands.py`'s own "one Reader call
plus presentation" discipline exactly, just producing JSON instead of
a formatted string.

## Package Structure

```
web/
    __init__.py
    server.py     start_server(host, port, ...) — ThreadingHTTPServer + routing
    api.py         handler functions: Reader/Workspace/Plugin calls -> dict (JSON-ready)
    static/
        index.html
        style.css
        app.js
```

## Internal API (the same one future IDE integrations can use)

Deliberately read-only with respect to shared state — see the
"repository selection never mutates the workspace" decision below.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/workspace` | registered repositories + which is active |
| GET | `/api/plugins?repo=<name>` | plugin records for that repository |
| GET | `/api/ask?repo=<name>&q=<query>` | `ComposedAnswer` (JSON) |
| GET | `/api/search?repo=<name>&q=<query>` | ranked `RetrievalMatch` list |
| GET | `/api/related?repo=<name>&id=<registry_id>` | direct neighbors |
| GET | `/api/explain?repo=<name>&q=<query>` | evidence + related with reasons |
| GET | `/api/health` | `{"status": "ok", "reader_version": "..."}` |

`repo` is optional on every endpoint except `/api/workspace`; omitted,
it resolves to the active workspace repository exactly like `cli.py`'s
`_resolve_repo_path` (falling back to the server's own `--repo`
startup argument, then cwd) — the same fallback chain, reused, not
reinvented.

**Repository selection never mutates `workspace.json`.** A browser tab
picking a different repository from the dropdown only changes the
`?repo=` query parameter on its own subsequent `fetch()` calls
(client-side JS state) — it never calls anything that changes the
*shared* active-repository pointer the CLI also reads. Two browser
tabs (or a browser tab and a terminal) looking at different
repositories at once must never fight over one shared "active" value.
This is why there is no `POST /api/repositories/<name>/use` endpoint —
selection is a read-only, per-client concern here, unlike `repo use`
in the CLI/REPL (a deliberate one-shot terminal action a user
explicitly asked to persist).

## Concurrency Safety (a real correctness question, not assumed away)

Two concurrent requests against the *same* repository could both
decide `.ocom/` needs rebuilding and both call `PersistentStore.save()`
at once — `save()` writes four files sequentially, not atomically, so
an interleaved pair of writers could produce a torn snapshot (one
request's `index.json` paired with another's `registry.json`). A
single process-wide `threading.Lock` around Reader construction (the
build-and-maybe-save step) closes this — a deliberate simplicity
choice over per-repository locking, the same "correct and simple
first" discipline M012 used for "Reader always resaves on
construction." Read-heavy concurrent load (the common case) only
serializes on this brief window, not on the whole request.

## Features → API Mapping

| Feature | Backed by |
|---|---|
| Repository selector | `GET /api/workspace` (client-side selection only, see above) |
| Ask/Search | `GET /api/ask`, `GET /api/search` |
| Answer view, Evidence panel, Related documents, Reading order | All four fields already on `ComposedAnswer` — one response, four panels |
| Plugin status | `GET /api/plugins` |
| Workspace status | `GET /api/workspace` |
| Dark mode | CSS `prefers-color-scheme` + a manual toggle (persisted in `localStorage`, client-only) |
| Responsive layout | CSS flexbox/grid + media queries, no framework |

Document *content* is never served — this pipeline has never indexed
full document bodies (M006's own boundary, restated as recently as
M015's `preview` field). Related documents render as title/path/reasons,
not clickable full-text, consistent with every prior CLI/REPL surface.

## Verification Plan

- `GET /api/ask` for the same query returns byte-identical JSON to
  what `reader.answer(query).model_dump(mode="json")` produces
  directly — proving "identical answers between CLI and Web UI" at
  the data level, not just by eyeballing rendered HTML.
- Multiple repositories: register two real repositories in the
  workspace, request `?repo=` for each, confirm independent results.
- Browser refresh: a full page reload must reproduce the same state
  from `localStorage` + a fresh `/api/workspace` call — no server-side
  session to lose.
- Concurrent requests: fire several real concurrent HTTP requests
  (Python `threading`/`concurrent.futures`, not simulated) against a
  running server, confirm no torn `.ocom/` snapshot and no crash.
- Plugin-enabled repository: a repository with a real (fixture)
  plugin registered, confirm `/api/plugins` reflects it.
- Manual, real-browser verification via the available browser tooling
  before writing automated tests — loading the actual page, clicking
  through Ask/Search, toggling dark mode, resizing for responsiveness.

## Test Plan

- `web/api.py` unit tests: each endpoint's handler function called
  directly (no real socket), covering success, missing repo, no
  active repository, unknown registry_id, empty query.
- `web/server.py` integration tests: a real `ThreadingHTTPServer`
  started on an ephemeral port, real HTTP requests via `urllib`/`http.client`,
  including the concurrency test above.
- Determinism/parity test: server response vs. direct `Reader` call,
  compared field-for-field.
- Real-repository verification (before writing the above): start the
  server against this project's own repository and at least one other
  real repository, drive it through the actual browser tool.

Proceeding to implementation now.
