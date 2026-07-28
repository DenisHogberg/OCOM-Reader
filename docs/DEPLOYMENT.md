# Deployment

Covers building and running the production image of Reader's Web UI. For how this
image plugs into the actual production Traefik/Docker Compose stack, see the
`OCOM-Infrastructure` repository — this document is scoped to the image itself, not
the infrastructure around it.

## Build

```bash
docker build -t ocom-reader:0.2.0 -t ocom-reader:latest .
```

Multi-stage: a `python:3.12-slim` builder stage produces a wheel via `python -m
build`, then a clean `python:3.12-slim` runtime stage installs only that wheel — no
build tooling ships in the final image. Runs as a non-root user (`ocom`).

## Run standalone (verification, not production)

```bash
docker run -d --name ocom-reader-test -p 18765:8765 ocom-reader:0.2.0
curl http://localhost:18765/api/health
curl "http://localhost:18765/api/search?q=identity"
curl "http://localhost:18765/api/ask?q=what+is+ocom+reader"
curl "http://localhost:18765/api/explain?q=registry"
docker rm -f ocom-reader-test
```

All four routes were verified this way against the real built image before this
document was written — see `READER_PRODUCT_READINESS.md`'s sibling report,
`READER_DEPLOYMENT_READINESS.md`, for the actual responses captured.

## What the container serves

`/app/docroot`, baked into the image at build time: this repository's own
`README.md`, `CHANGELOG.md`, `READER_*.md` reports, and `docs/`. Nothing else —
no Vector repository is ever mounted or referenced by this image. This is
intentional, not a placeholder: a publicly reachable Reader instance must only ever
show non-corporate example content, and the web UI has no Vector integration to
accidentally expose in the first place.

## Environment variables

None required. `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are read only by the optional LLM
Normalizer — a code path the web UI (`/api/ask`, `/api/search`, `/api/explain`) never
calls.

## Health check

`GET /api/health` → `{"status": "ok", "reader_version": "0.2.0"}`. Wired into the
image's own `HEALTHCHECK` (30s interval, 3 retries) and suitable for Traefik or any
external load balancer to probe directly.

## Rollback

Because this image is not yet wired into the production stack (`ocom-placeholder`
still serves `ocom.uno` behind Traefik — see `OCOM-Infrastructure`'s
`docs/CLEANUP.md` for the current cutover gate), there is nothing running in
production to roll back yet. Once it *is* deployed as `reader-placeholder`'s
replacement in `OCOM-Infrastructure`'s `docker-compose.yml`, rollback is:

1. `docker compose -f docker-compose.yml stop reader` (or whatever service name
   replaces `reader-placeholder`).
2. Revert `docker-compose.yml`'s `reader` service definition to the previous
   commit (`git checkout <previous-commit> -- docker-compose.yml` in
   `OCOM-Infrastructure`, or `git revert` the swap commit).
3. `docker compose up -d` — recreates `reader-placeholder` from the restored
   config; Traefik's router (`reader@docker`, unchanged throughout) picks it up on
   its next health check with no manual Traefik intervention.

Because the router labels, network, and TLS resolver never change between the
placeholder and the real image, rollback is a one-service `docker compose` revert,
not an infrastructure change.
