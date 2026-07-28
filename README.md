# OCOM Reader

![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)
![Tests](https://github.com/DenisHogberg/OCOM-Reader/actions/workflows/tests.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.2.0-informational.svg)

OCOM Reader is a CLI (and small Web UI / library) for asking deterministic,
rule-based questions about a repository's own Markdown documentation, and for
reading, searching, and reviewing operational data produced by a separate project
called **Vector**. **Reader reads Vector's data; it is a separate, independent
project and never modifies anything Vector produces.**

## Why Reader?

Two related but distinct problems, solved without an LLM in the loop by default:

- A repository accumulates real architectural knowledge in its own Markdown docs, and
  finding the right one by grep alone gets harder as it grows. Reader indexes a
  repository's own documentation and answers questions about it deterministically —
  the same query against an unchanged repository always produces byte-identical
  output, with no LLM, embeddings, or semantic search required.
- Separately, a company using **Vector** (an OCOM-based operational memory platform —
  meetings, decisions, tasks, risks, and more, extracted from real transcripts) needs a
  way to browse, search, and review that data without writing more code against
  Vector's raw files directly. Reader's `vector` subcommand is that read-only client.

## Reader vs Vector

These are two separate GitHub repositories with two separate purposes:

| | Reader (this repository) | Vector |
|---|---|---|
| What it is | An open-source CLI/library — a *consumer* of data | A private, proprietary operational memory platform — a *producer* of data |
| What it does | Reads, searches, and displays | Ingests real meeting transcripts, extracts Statements, stages them for human review |
| Writes to Vector? | **Never.** Read-only, always. | — |
| License | Apache-2.0 (this repository) | Proprietary, all rights reserved (Vector's own repository) |

Reader talks to Vector only through a versioned, documented contract
(`docs/vector-integration.md`) — never by assuming Vector's internal implementation
details. A Vector repository is just a directory on disk you point Reader at; Reader
never requires network access to it.

## Features

- **Deterministic Q&A over a repository's own docs** — `ask`/`search`/`explain`/
  `related`, no LLM required (an optional LLM presentation layer exists — see
  `docs/HISTORY.md`).
- **Vector integration** — signal-based search and browsing, object navigation
  (Object View, cross-meeting mentions, a relationship browser, an entity timeline),
  and a Promotion Review queue — 10 `vector` subcommands, all read-only.
- **Multi-repository workspace** — register and switch between repositories by name
  (`repo add`/`use`) instead of retyping paths.
- **A plugin system** and **a small local Web UI**, both built on the same core.

## Installation

Requires Python 3.9+. Not yet published to PyPI — install from a clone:

```bash
git clone https://github.com/DenisHogberg/OCOM-Reader.git
cd OCOM-Reader
pip install -e .
```

## Quick Start (5 minutes)

```bash
# 1. Ask Reader about its own documentation — no external data needed.
ocom-reader ask "identity resolution"

# 2. Point Reader at a separate Vector repository you have on disk.
#    (Substitute your own path — any directory containing Vector's
#    objects/ and/or ai/staging/ trees works.)
ocom-reader vector stats path/to/vector-repo

# 3. Run your first genuinely useful Vector command: see what a human
#    should review next, grouped by what Vector's own pipeline detected.
ocom-reader vector review path/to/vector-repo
```

That's the whole loop: install, ask Reader something about itself, then point it at
Vector and get a real, useful answer back. Everything past this point is optional
depth, not required to start using Reader.

## CLI Overview

Reader has four command groups. This is a tour, not the full reference — run
`ocom-reader <command> --help` for every flag, or see `docs/vector-integration.md` for
the complete, versioned Vector command reference.

| Command | Does |
|---|---|
| `ask` / `search` / `explain` / `related` | Deterministic Q&A over a repository's own Markdown docs |
| `repo add` / `use` / `list` / `remove` | Register repositories by name, switch the active one |
| `vector show` / `search` / `signals` / `summary` / `stats` | Read and search Vector Statements by signal |
| `vector object` / `mentioned-in` / `relationships` / `timeline` | Navigate Vector objects and their relationships |
| `vector review` | Group Statements by `statement_kind` for human promotion review |
| `plugin list` / `info` / `enable` / `disable` / `reload` | Manage the plugin system |
| `web` | Start the local Web UI (`http://127.0.0.1:8765`) |

Also usable as a library — `from ocom_reader.reader import Reader` — see
`docs/HISTORY.md`'s "Programmatic use" section for a runnable example.

## Working with Vector

Every `vector` subcommand takes a path to a Vector repository (or a subdirectory of
one, such as one Meeting's staging folder) and is read-only:

```bash
ocom-reader vector show path/to/STM-....md            # one Statement, full detail
ocom-reader vector search path/to/vector-repo --signal task
ocom-reader vector object path/to/vector-repo PTN-20260727-A1NG
ocom-reader vector review path/to/vector-repo          # the Promotion Review queue
```

Reader currently reads two things beyond what Vector's contract formally covers yet
(`Meeting.meeting_date`, and the common object schema `VectorObject` relies on) — both
flagged explicitly, both optional/tolerant of absence. Full guarantees, compatibility
notes, and every command's exact output format: **`docs/vector-integration.md`**.

## Architecture Overview

```
Repository -> RepositoryIndex -> KnowledgeRegistry -> RetrievalEngine -> AnswerComposer -> Reader / CLI
                                                                                  ↑
Vector repository -> vector_integration/ (loader, signals, navigation, promotion) ┘
```

Two independent pipelines share one CLI and one `Reader` facade: the original
Adapter/Normalizer core plus the deterministic documentation-Q&A pipeline built on top
of it, and the separate, read-only `vector_integration/` package this repository's
recent milestones (M01-M04) added. Neither pipeline's internals leak into the other.

The full historical narrative — the Adapter/Normalizer core, Phases 1-5, and the
original architectural principles this project started from — is preserved in
**`docs/HISTORY.md`**, not deleted, just moved out of this file so it doesn't crowd out
getting started. Design docs for every individual milestone live in
[`docs/architecture/`](docs/architecture/) (the original M006-M021 track) and this
repository's root `READER_M0X.md`/`READER_M0X_DESIGN.md` files (the Vector-integration
track, M01-M04 — a separate, restarted count; see `CHANGELOG.md`'s "Project History"
section if the two numbering schemes are ever confusing side by side).

## Current Status

512 tests passing. Implemented: the Reader MVP (deterministic Q&A), extensibility
(multi-repo workspace, plugins), a Web UI, an optional LLM layer, and the Vector
integration (M01 Contract Compliance through M04 Promotion Review UI).

**Known limitations**, checked directly against real data, not assumed: Vector's real
`relationships` and `alias:` tags are currently unpopulated (0 of 6 real objects have
either), so the Relationship Browser has nothing real to show yet; speaker identity is
unresolved on Vector's side, so `speaker:` search won't match a real name yet; Vector
has no persisted "Promotion Candidate" data, so `vector review` groups by
`statement_kind` only, deliberately, rather than inventing a richer classification
Reader has no contracted basis for.

Full detail, including exactly which fields are contracted versus flagged exceptions:
**`READER_STATUS.md`**.

## Production

A `Dockerfile` builds a production image of the Web UI (`ocom-reader web --host 0.0.0.0
--port 8765`), independent of any Vector repository:

```bash
docker build -t ocom-reader:local .
docker run --rm -p 8765:8765 ocom-reader:local
curl http://localhost:8765/api/health
```

Or via the included example compose file: `docker compose -f docker-compose.example.yml
up --build`.

**What the container serves**: this repository's own documentation (`README.md`,
`CHANGELOG.md`, the `READER_*.md` reports, and `docs/`) — baked into the image at
`/app/docroot`, indexed by Reader itself. No Vector repository is mounted or
referenced; the web UI has no Vector wiring today, so this is also the only content it
is capable of serving. This is a deliberate choice, not a placeholder: a public
deployment of Reader must only ever show non-corporate example content.

**No environment variables are required.** `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are
read only by the optional LLM Normalizer, a code path the web UI never calls.

**Health check**: `GET /api/health` → `{"status": "ok", "reader_version": "0.2.0"}`,
wired into the image's `HEALTHCHECK` and suitable for an external load balancer /
reverse proxy health probe.

This repository does not deploy itself anywhere — see the `OCOM-Infrastructure`
repository for the actual production Traefik/Docker Compose stack this image plugs
into.

## Documentation

- **`docs/vector-integration.md`** — the Vector integration's supported contract
  version, compatibility guarantees, and every command's exact output.
- **`docs/HISTORY.md`** — the original Adapter/Normalizer core narrative (Phases 1-5)
  and early architecture, preserved in full.
- **[`docs/architecture/`](docs/architecture/)** — per-milestone design docs for the
  original Reader-core track (M006 through M021).
- **`READER_STATUS.md`** — capabilities, contract dependencies, and limitations at a
  glance.
- **`READER_M01.md`** through **`READER_M04.md`**, plus **`READER_M04_DESIGN.md`** —
  the Vector-integration milestone reports, including the design-review-before-code
  discipline established for M04 onward.
- **`READER_ROADMAP_REVIEW.md`**, **`READER_PRODUCT_READINESS.md`** — the analysis
  behind why this Product Readiness sequence (License → CI → Changelog → this README)
  happened, and in this order.
- **`CHANGELOG.md`** — every notable change, and an explicit note on this project's two
  overlapping milestone-numbering schemes.

## Roadmap

Per `READER_ROADMAP_REVIEW.md`'s own conclusion: stabilize before adding new
analytical features. Product Readiness is in progress — License (P01) and CI (P02) and
Changelog & Versioning (P03) are done; this README (P04) is the last item identified
before Reader is genuinely ready for its first public release. No M05 has been
scoped or design-reviewed yet.

## License

Apache License, Version 2.0 — see [`LICENSE`](LICENSE). Rationale for choosing
Apache-2.0 over MIT/BSD-3-Clause: `READER_LICENSE_REVIEW.md`.
