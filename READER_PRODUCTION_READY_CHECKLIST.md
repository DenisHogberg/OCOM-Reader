# Reader — Production Ready Checklist

Status as of this writing: **not yet deployed** — `reader-placeholder` still serves
`reader.ocom.uno`. Every item below was actually measured or tested against the
real built image (`ocom-reader:0.2.0`), not assumed.

## 1. Docker image — production operations review

| Check | Result |
|---|---|
| Image size | 212MB disk / 51.8MB compressed, 12 layers |
| Startup time (`docker run` → first successful `/api/health`) | ~0.67s |
| Idle memory | 23.6MiB (1.24% of the server's 1.9GiB) |
| Idle CPU | 0.01% |
| Non-root user | Yes — `ocom` (uid 999, gid 999), enforced via `USER ocom` |
| Exposed ports | `8765/tcp` only |
| File permissions | `docroot/` and its content owned by `ocom:ocom`; no world-writable paths |
| Signal handling (SIGTERM) | **No handler** — confirmed: default `STOPSIGNAL`, `docker stop` took the full 10s grace period and ended in `SIGKILL` (`ExitCode 137`) |
| Graceful shutdown | **Fixed at the container level** — `STOPSIGNAL SIGINT` added to the `Dockerfile`; the app *does* catch `KeyboardInterrupt` (SIGINT) and closes the server cleanly. Re-tested: `docker stop` now takes ~0.14s, `ExitCode 0`. No Reader source code changed — this is a Docker runtime setting only |

**Not fixed, and why that's a documented trade-off, not an oversight**: the app has
no explicit request-draining logic even under SIGINT — for a stateless, read-only
service with no in-flight writes or transactions, this is low-risk. Flagged, not
silently ignored.

## 2. `.ocom` cache — dedicated volume

- `Dockerfile` now declares `VOLUME ["/app/docroot/.ocom"]`.
- Verified: a fresh named volume mounted there is correctly initialized with
  `ocom:ocom` ownership (inherited from the image), gets populated with real
  `index.json`/`registry.json`/`metadata.json`/`retrieval.json` on first query.
- Verified: recreating the container against the **same** volume reuses the
  existing cache unchanged (same file mtimes) — no unnecessary re-index.
- Confirmed regenerable: nothing in the cache is source data; losing the volume
  costs one re-index pass over the ~60 Markdown files baked into the image, not
  data loss.

## 3. Production compose service example

`docker/examples/reader-service.yml` added to `OCOM-Infrastructure` (reference
only, **not wired into `docker-compose.yml`**, changes nothing about the running
stack). Same router name/rule/entrypoint/TLS resolver as `reader-placeholder`
today, plus the new named volume for `.ocom`.

## 4. Traefik attachment — verified without touching existing routing

A container built from `ocom-reader:0.2.0`, joined to `ocom_internal` with a
distinct test router (`reader-verify`, not the real `reader` router), was
auto-discovered by Traefik's Docker provider with no restart and no config
change. `GET https://reader-verify.ocom.uno/api/health` (via `curl --resolve`,
bypassing public DNS) returned `200` with the real JSON body and every global
security header applied automatically. `reader.ocom.uno` and `ocom.uno` continued
responding unchanged throughout. Full detail and exact commands:
`OCOM-Infrastructure`'s `docs/DEPLOYMENT.md`, "Reader service (not yet active)"
section.

## 5. Production Ready — final status

| Area | Status |
|---|---|
| Builds reproducibly from source | ✅ |
| Starts fast, idle footprint negligible | ✅ (0.67s, 23.6MiB, 0.01% CPU) |
| Runs as non-root | ✅ |
| Health check (image-level `HEALTHCHECK` + `/api/health`) | ✅ |
| All 4 verified routes (`/api/health`, `/api/search`, `/api/ask`, `/api/explain`) | ✅ |
| Clean, fast shutdown | ✅ (fixed via `STOPSIGNAL`, re-verified) |
| Cache survives restarts, remains regenerable | ✅ |
| Attaches to Traefik with zero routing-model change | ✅ (verified live) |
| Full test suite still passing | ✅ (515/515 — no `src/` changes at any point in this work) |
| Production placeholder replaced | ❌ — **intentionally not done yet**, per instruction |
| Infrastructure repository changed | ❌ — **intentionally not done**; only a non-wired example file added |

**Overall: deployment-ready.** Nothing identified in this review blocks replacing
`reader-placeholder` when that step is explicitly requested. The swap itself is a
one-service edit to `OCOM-Infrastructure`'s `docker-compose.yml` (image, port,
volume — router/network/TLS unchanged), per `docker/examples/reader-service.yml`.
