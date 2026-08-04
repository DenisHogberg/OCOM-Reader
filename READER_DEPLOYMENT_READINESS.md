# Reader Deployment Readiness — Container Verification Report

**Status:** Verified against a real built image, not simulated. No functionality
changed, no Companion integration added, no infrastructure modified, the production
placeholder was not replaced.

## What was built

`Dockerfile` (multi-stage, `python:3.12-slim`), `.dockerignore`,
`docker-compose.example.yml`, a `README.md` "Production" section, and this report.
Built as `ocom-reader:0.2.0` / `ocom-reader:latest` on the production server (build
host only — the image was never attached to the running Traefik network or
production compose stack).

## Verification results

| Check | Result |
|---|---|
| `docker build` | Succeeded, image size 212MB disk / 51.8MB compressed |
| Container starts, `docker ps` shows `Up` | Confirmed |
| `GET /api/health` | `{"status": "ok", "reader_version": "0.2.0"}` |
| `GET /api/search?q=identity` | Real matches returned (ADR-005, ADR-004, ADR-006 — this repo's own docs) |
| `GET /api/ask?q=what+is+ocom+reader` | Real composed answer, citing `README.md` with match reasons |
| `GET /api/explain?q=registry` | Real matches (MILESTONE-007-DESIGN.md and others), with reasons |
| Docker `HEALTHCHECK` | `healthy` after settling |
| Container logs | No errors |
| Full test suite (`pytest`, local, before and after these changes) | 515/515 passed |
| Production stack (`traefik`, `ocom-placeholder`, `reader-placeholder`) | Confirmed untouched — same 3 containers, same status, throughout |

One real bug was found and fixed during verification, not assumed correct in
advance: the initial `ENTRYPOINT` placed `--repo` after the `web` subcommand;
`--repo` is actually a global flag defined before `argparse`'s subparsers, so the
container exited immediately with `unrecognized arguments: --repo /app/docroot`.
Fixed by reordering to `ocom-reader --repo /app/docroot web --host 0.0.0.0 --port
8765`, rebuilt, reverified — all four routes above are from the corrected image.

## Readiness by the original 8-point assessment

| # | Item | Before | Now |
|---|---|---|---|
| 1 | Application type | CLI + optional web UI | Unchanged — this doesn't turn it into "a web app," it packages the same CLI's `web` subcommand |
| 2 | Deployable as Docker service | No | **Yes** — built, run, and verified |
| 3 | Runtime | Python ≥3.9 | Image uses 3.12, satisfies the constraint |
| 4 | Dockerfile | No | **Yes**, multi-stage |
| 5 | Health endpoint | Yes (`/api/health`), untested in a container | Yes, now also verified through Docker's own `HEALTHCHECK` |
| 6 | Required env vars | None for the web path | Unchanged — none required |
| 7 | Persistent storage | `.ocom/` cache, regenerable | Present inside the image at `/app/docroot/.ocom`; not yet mounted as an external volume (see below) |
| 8 | Missing components | 5 gaps listed | All 5 addressed except the production WSGI-server caveat, which was flagged as acceptable-for-now, not fixed — see below |

## What's still genuinely open, not glossed over

- **`.ocom/` is currently image-internal, not a mounted volume.** Every container
  restart rebuilds the index from `/app/docroot`'s ~60 Markdown files — cheap at this
  size, but worth mounting a named volume once deployed for real, so restarts don't
  pay that cost repeatedly.
- **Still no production WSGI/ASGI server** — `ThreadingHTTPServer` remains the
  runtime. Fine for the traffic level of a single public documentation instance;
  revisit if real usage ever suggests otherwise.
- **The image was built and tested on the production server itself, standalone** —
  not yet through the `OCOM-Infrastructure` repository's own build/deploy path
  (there is no CI step building this image yet; `.github/workflows/deploy.yml` in
  `OCOM-Infrastructure` only redeploys existing services, it doesn't build new
  images). Wiring an actual build step is part of the next phase (replacing
  `reader-placeholder`), not this one.

## Explicit confirmation of constraints honored

- Reader's functionality: unchanged — no file under `src/` was modified.
- Companion integration: not touched, not added — `/app/docroot` contains this
  repository's own docs only.
- Infrastructure architecture: not modified — `OCOM-Infrastructure`'s
  `docker-compose.yml`, Traefik config, and network were not changed.
- Production placeholder: not replaced — `reader-placeholder` (`nginx:1.27-alpine`)
  is still what `reader.ocom.uno` resolves to.
