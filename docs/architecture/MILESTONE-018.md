# MILESTONE-018: Web UI

**Date:** 2026-07-24
**Status:** Frozen — the browser is another Reader client; zero new dependencies; Reader pipeline untouched.
**Builds on:** [MILESTONE-018-DESIGN.md](MILESTONE-018-DESIGN.md), [MILESTONE-017](MILESTONE-017.md), [MILESTONE-016](MILESTONE-016.md)

## Objective

A lightweight Web UI on top of the existing Reader API. The browser is
another client of `Reader` — not another implementation. No
browser-facing code performs retrieval, ranking, persistence,
repository indexing, or plugin loading.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `resolve_repo_path`, `get_health/workspace/plugins/ask/search/related/explain`, `ApiError` | `web/api.py` | New |
| `start_server`, `make_handler` (`ThreadingHTTPServer` + router) | `web/server.py` | New |
| `index.html`, `style.css`, `app.js` | `web/static/` | New |
| `ocom-reader web [--host] [--port]` | `cli.py` | Revised |

`retrieval/`, `registry/`, `indexer/`, `composer/`, and every other
M001-M017 package — all unchanged, confirmed via `git diff --stat`
(empty for every one of them). A `grep` for direct
`retrieval`/`registry`/`indexer`/`composer` imports in `web/` returns
nothing — `web/api.py` only ever imports `Reader`, `WorkspaceManager`,
`PluginManager`, exactly mirroring `cli.py`'s own import discipline.

## Two Decisions Flagged Up Front (both held)

1. **Zero new dependencies.** `http.server.ThreadingHTTPServer` (stdlib)
   for the backend, static HTML/CSS/vanilla JS for the frontend — no
   Flask/FastAPI, no npm/node, no build step. `pyproject.toml` still
   depends on `pydantic` alone.
2. **Binds to `127.0.0.1` by default**, never `0.0.0.0` — this
   project's first network listener, and a local documentation tool
   has no reason to be reachable from the local network by default.
   `--host`/`--port` are exposed for a caller who explicitly wants
   otherwise.

## Internal API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "reader_version": "..."}` |
| GET | `/api/workspace` | registered repositories + active |
| GET | `/api/plugins?repo=` | plugin records |
| GET | `/api/ask?repo=&q=` | `ComposedAnswer` JSON |
| GET | `/api/search?repo=&q=` | ranked matches |
| GET | `/api/related?repo=&id=` | direct neighbors |
| GET | `/api/explain?repo=&q=` | evidence + related with reasons |

Every handler is one Reader/WorkspaceManager/PluginManager call plus
`.model_dump(mode="json")` — no new matching, ranking, or composition
logic, the same "one call plus presentation" discipline `commands.py`
already established for the CLI.

**Repository selection never mutates `workspace.json`.** There is no
`POST /api/repositories/<name>/use` — the browser's `?repo=` selection
is client-side (`localStorage`) only. Verified directly, not assumed:
`test_selecting_a_repository_never_mutates_the_workspace_active_pointer`
switches repositories via the API and then reloads a fresh
`WorkspaceManager` from the same state file, confirming `active` is
unchanged.

## Concurrency Safety — a Real Race, Closed

Two concurrent requests against the same repository could both decide
`.ocom/` needs rebuilding and both call `PersistentStore.save()` at
once (it writes four files sequentially, not atomically) — a real risk
for a threaded server that wasn't a concern for the single-shot CLI. A
process-wide `threading.Lock` around Reader construction closes it.
Verified with real concurrent load, not simulated: 20 real threads
hitting the same repository through real HTTP requests, then loading
the resulting `.ocom/` snapshot directly and confirming index/registry
entry counts match (`test_concurrent_writes_to_the_same_repository_produce_a_consistent_snapshot`).

## Features → What Backs Them

Repository selector, Ask/Search/Explain, Answer/Evidence/Related
Documents/Reading Order panels, Plugin status, Workspace status, dark
mode, responsive layout — all implemented and manually verified live
in a real browser (below) before any automated test was written.
Document *content* is never served (this pipeline has never indexed
full document bodies, M006's own boundary) — related documents render
as title/path/reasons, consistent with every prior CLI/REPL surface.

## Real-Browser Verification (Before Any Test Was Written)

Using the actual browser tool, not a headless assumption:

- Loaded the page against a workspace with two real repositories
  (this project, `/Users/mac/OCOM.wiki`) registered.
- `ask "identity resolution"` rendered Answer/Evidence/Related
  Documents/Reading Order correctly, including markdown-rendered
  previews (`**Status:**` → bold, `` `ResolutionRequest` `` → inline
  code).
- Switched the repository selector to `wiki` and re-asked — results
  correctly came from the wiki repository, confirmed via
  `get_page_text`, and the shared `workspace.json` was confirmed
  unchanged on disk afterward.
- Dark mode toggle switched the whole page's theme and persisted
  across a page reload.
- Resized to a mobile viewport (375×812) — layout correctly collapsed
  to a single column with the sidebar reordered above the main
  content.
- 40 real concurrent HTTP requests (Python `concurrent.futures`, real
  threads, real sockets) all returned 200 with non-empty bodies.
- `GET /api/ask` output compared field-for-field against
  `Reader(...).answer(...).model_dump(mode="json")` called directly —
  identical.

One transient screenshot glitch (a blank capture) was investigated via
`get_page_text` before assuming a bug — the page content was correct;
the screenshot tool itself hiccuped. Named here so it isn't mistaken
for a real finding.

## Test Results

- `tests/test_web_api.py`: **19 passed** — `resolve_repo_path` (by
  name, unknown name, active fallback, default fallback), every
  handler function (success and missing-parameter paths),
  `get_ask`/direct-`Reader` output equality, and the construction lock
  under 10 real concurrent threads.
- `tests/test_web_server.py`: **21 passed** — real `ThreadingHTTPServer`
  on an ephemeral port: static file serving (index.html, app.js, 404
  for unknown paths, path-traversal blocked), every API endpoint,
  unknown `repo` query param, multiple repositories via `?repo=`, the
  no-mutation-of-active guarantee, CLI/API determinism and parity, 30
  real concurrent requests, real concurrent *writes* producing a
  consistent snapshot, and a real-repository integration test.
- `tests/test_cli.py`: **1 new** — the `web` subcommand wiring itself
  (`start_server` called with the right arguments, `serve_forever`
  invoked exactly once, clean shutdown) — `serve_forever` stubbed only
  here to avoid blocking the test process; the server's actual
  behavior is already covered end-to-end by `test_web_server.py`'s
  real sockets.
- Full suite: **430 passed** (389 before this milestone + 41), no
  regressions.

## Known Limitations

- **No `HEAD` method support** — `BaseHTTPRequestHandler` only
  implements `do_GET`; a `HEAD` request (e.g. `curl -I`) gets a 501.
  Browsers use `GET` for navigation, so this doesn't affect real usage;
  named because it was observed directly during verification, not
  guessed at.
- **Single global construction lock**, not per-repository — a
  deliberate simplicity choice (see design doc); under heavy
  concurrent load against *many different* repositories at once, reads
  briefly serialize on this lock even though they touch unrelated
  repositories. Not measured to matter at this scale; a candidate for
  later refinement if it ever does.
- **No document content view** — consistent with every prior surface;
  this pipeline has never indexed full document bodies.
- **No authentication** — appropriate for a `127.0.0.1`-only local
  tool; would need real consideration before `--host 0.0.0.0` is ever
  used for anything beyond local testing.

## Roadmap

```
✅ M001-M017 — OCOM Reader MVP + Repository Independence + Retrieval Evolution + Extensibility (frozen)
✅ M018 Web UI — this document
⬜ M019 Optional LLM Layer
⬜ M020 Product Release
```
