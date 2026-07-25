# MILESTONE-019: Optional LLM Layer

**Date:** 2026-07-25
**Status:** Frozen — presentation-only natural-language generation; `Reader` itself has zero diff.
**Builds on:** [MILESTONE-019-DESIGN.md](MILESTONE-019-DESIGN.md), [MILESTONE-018](MILESTONE-018.md)

## Objective

Optional natural-language generation with zero changes to the
deterministic execution path. `Reader` gains no new parameter, method,
or import — verified with `git diff --stat` showing an empty diff for
`reader.py`, not just claimed.

## Architecture

```
Repository
      ↓
Reader
      ↓
Retrieval
      ↓
Composer
      ↓
ComposedAnswer
      ↓
LLM Adapter (optional)
      ↓
Presentation
```

The LLM sits after `ComposedAnswer`, not inside the pipeline that
produces it. Everything above `ComposedAnswer` is exactly the same
pipeline M001-M018 already built and froze; the LLM Adapter is a
presentation-layer append, never a participant in it.

## Architectural Invariants

The real result of this milestone is not the LLM integration itself,
but the fact that it is confined to a fully optional presentation
layer. This is not a recommendation — it is one of OCOM Reader's core
architectural principles, and it is recorded here explicitly:

1. **The optional LLM layer must never perform evidence search or
   retrieval.** `LLMAdapter` has no handle to `RetrievalEngine`,
   `KnowledgeRegistry`, or `RepositoryIndex` — structurally, not by
   convention (see "The One Rule, Held" above).
2. **The optional LLM layer must never modify evidence.**
   `LLMAdapter.enhance()` takes `ComposedAnswer` and never mutates it —
   enforced and tested (`test_enhance_never_mutates_the_composed_answer`,
   both on success and on failure).
3. **The optional LLM layer must never rank or filter evidence.** It
   receives `answer.evidence`/`related_documents`/`reading_order`
   exactly as `Composer` produced them, for prompt-building only; it
   has no ranking or filtering logic of its own anywhere in `llm/`.
4. **The optional LLM layer must never replace deterministic answer
   composition.** `LLMResult.text` is an *additional* field returned
   alongside the untouched `ComposedAnswer`, never a substitute for
   it. CLI output always renders the full deterministic
   Answer/Evidence/Related Documents/Recommended Reading Order
   sections first; a successful LLM result only ever appends a further
   "Natural Language Answer" section
   (`test_ask_llm_provider_never_changes_deterministic_evidence_or_reading_order`).
5. **The optional LLM layer must never become a required system
   dependency.** Base installation depends on `pydantic` alone;
   `openai`/`anthropic` are `[project.optional-dependencies]` extras.
   Confirmed directly, not assumed: neither SDK is installed in this
   environment, and the full test suite — including every LLM test —
   passes regardless.
6. **The architecture must guarantee the LLM layer is structurally
   incapable of influencing Retrieval, Indexing, Registry Resolution,
   or Evidence Composition.** Verified mechanically at the end of this
   milestone, the same discipline M017 established for the plugin
   layer: `git diff --stat` shows an empty diff for `reader.py`,
   `retrieval/`, `registry/`, `indexer/`, and `composer/`, and a grep
   for actual imports of `RetrievalEngine`/`KnowledgeRegistry`/`RepositoryIndexBuilder`/`AnswerComposer`
   inside `llm/` returns nothing but docstring prose stating the
   constraint — never an import.

## Implemented Components

| Component | File | Status |
|---|---|---|
| `LLMProviderName`, `LLMConfig`, `LLMResult` | `llm/models.py` | New |
| `LLMProvider` (Protocol) | `llm/protocol.py` | New |
| `LLMError`, `LLMProviderUnavailableError` | `llm/exceptions.py` | New |
| `LLMAdapter` | `llm/adapter.py` | New |
| `OpenAIProvider` | `llm/providers/openai.py` | New |
| `AnthropicProvider` | `llm/providers/anthropic.py` | New |
| `ask --llm-provider {openai,anthropic}` | `cli.py` | Revised |
| `[project.optional-dependencies]` (`openai`, `anthropic`) | `pyproject.toml` | Revised |

`reader.py`: **zero diff.** `retrieval/`, `registry/`, `indexer/`,
`composer/`, `web/`: all zero diff. A grep for actual imports of
`RetrievalEngine`/`KnowledgeRegistry`/`RepositoryIndexBuilder`/`AnswerComposer`
in `llm/` returns only docstring prose explaining the constraint, not
imports — `llm/adapter.py` imports exactly one thing from outside
`llm/`: `ComposedAnswer`, a plain pydantic data model, the same class
`cli_output.py` already imports for rendering.

## The One Rule, Held

`LLMAdapter` never receives a `Reader`, `RetrievalEngine`,
`KnowledgeRegistry`, or `RepositoryIndex` — only an already-built
`ComposedAnswer`. It structurally cannot retrieve, search, rank, or
invent evidence, because it has no handle to anything that could do
those things. Same structural guarantee M017 gave the plugin layer,
applied here.

## No Provider Required for Installation

`pyproject.toml`'s base dependencies remain `pydantic` alone.
`openai`/`anthropic` are `[project.optional-dependencies]` extras —
installable (`pip install ocom-reader[openai]`), never required.
Confirmed directly in this environment: neither SDK is installed
(`ModuleNotFoundError` for both), making "provider unavailable" a
**real**, not simulated, test scenario throughout this milestone.

## A Real Bug Found During Verification (and fixed)

`LLMAdapter.enhance()`'s hard timeout was originally implemented with
`with ThreadPoolExecutor(...) as pool:`. Manual verification with a
provider that sleeps 2 seconds and a 0.2-second configured timeout
showed the call still took **2.01 seconds**, not ~0.2s — the
context manager's `__exit__` calls `shutdown(wait=True)`, which blocks
until the already-running background thread finishes, silently
defeating the timeout it was supposed to enforce. Fixed by managing
the executor manually and calling `shutdown(wait=False)` in a
`finally` block, so `enhance()` returns as soon as `future.result()`
times out — re-verified afterward at **0.205s**. The orphaned thread
finishes on its own in the background; Python has no way to forcibly
kill a running thread, an honest, named limitation, not hidden. Named
in full here rather than silently patched, the same discipline M013's
late-binding bug, M015's paging hang, and M017's discovery-isolation
bug were all handled.

## Configuration — No `api_key` Field, By Design

```python
class LLMConfig(BaseModel):
    provider: LLMProviderName = LLMProviderName.DISABLED
    model: Optional[str] = None
    timeout_seconds: float = 10.0
```

Keys are read *only* from `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`
environment variables, inside each provider's own `__init__` — never a
CLI argument (would leak into shell history/process listings), never
part of any persisted config. `LLMConfig` is never written to
`.ocom/`, `workspace.json`, or `plugins_state.json`.

## Fallback — `enhance()` Never Raises

Every failure mode (disabled, SDK not installed, no API key, network
error, API error, timeout) produces an `LLMResult(text=None, fallback_reason=...)`,
never an exception the caller must catch. Verified for every path:
`test_provider_raising_falls_back_gracefully`,
`test_timeout_falls_back_gracefully_and_does_not_block_the_caller`,
`test_adapter_falls_back_gracefully_when_openai_sdk_is_not_installed`,
`test_adapter_falls_back_gracefully_when_anthropic_sdk_is_not_installed`.

## CLI Integration

```bash
ocom-reader ask "..."                          # unchanged
ocom-reader ask "..." --llm-provider openai     # opt-in, falls back gracefully if unavailable
ocom-reader ask "..." --llm-provider anthropic
```

`--llm-provider` defaults to unset. When set and the enhancement
succeeds, a "Natural Language Answer" section is *appended* after the
existing deterministic Answer/Evidence/Related Documents/Recommended
Reading Order sections — never replacing them.
`test_ask_llm_provider_never_changes_deterministic_evidence_or_reading_order`
confirms the deterministic output is a byte-identical *prefix* of the
LLM-flagged output, not merely "similar."

## Test Results

- `tests/test_llm_adapter.py`: **16 passed** — protocol conformance,
  disabled-by-default, success with a fake provider, prompt content
  bounded to `ComposedAnswer` fields only, the "must not invent facts"
  instruction present, provider-raises fallback, the timeout
  regression test (asserting `elapsed < 1.0` against a 2s-delay fake
  provider), real `LLMProviderUnavailableError` from both real
  provider classes (SDK not installed), the adapter's own graceful
  fallback through the real (non-injected) construction path for both
  providers, a monkeypatched-SDK test for the "installed but no API
  key" path, `ComposedAnswer` never mutated (success and failure), and
  determinism with a deterministic fake provider.
- `tests/test_cli.py`: **5 new** — flag-omitted output is stable
  across repeated runs with no "Natural Language Answer" text present,
  graceful fallback for both `openai` and `anthropic` with all
  deterministic sections still present, a successful-provider path
  (fake `LLMAdapter` injected via monkeypatch) confirming the new
  section is appended, and the byte-identical-prefix check above.
- Full suite: **451 passed** (430 before this milestone + 16 + 5), no
  regressions — the entire pre-existing suite unmodified.

## Real-Repository Verification

Before writing any test: ran `ocom-reader ask ... --llm-provider openai`
and `--llm-provider anthropic` against this project's own repository
and `/Users/mac/OCOM.wiki`, confirming in both cases: exit code 0, a
clear "(LLM unavailable: ... — showing deterministic answer only)"
message, and every deterministic section (Answer/Evidence/Related
Documents/Recommended Reading Order) fully present and correct.

## Security Considerations

- **API keys**: environment variables only, never CLI arguments, never
  persisted anywhere on disk.
- **Data sent to a provider**: only what's already in `ComposedAnswer`
  (query text, evidence titles/paths/reasons, related documents,
  reading order) — no raw file content (never indexed to begin with),
  no repository paths beyond what evidence already contains.
- **Installation footprint**: a base `pip install ocom-reader` never
  pulls in either provider SDK.
- **Time-bounded**: every provider call is wrapped in a hard,
  adapter-enforced timeout, not trusted to the SDK's own timeout
  parameter (which the bug above showed isn't sufficient on its own to
  bound the *caller's* wait time).

## Known Limitations

- **No true thread cancellation.** A timed-out provider call's
  background thread keeps running until it naturally finishes (or the
  process exits) — Python cannot forcibly kill a thread. The caller is
  never blocked by this, but the thread isn't instantly gone either.
- **CLI wiring is `ask`-only.** `search`/`explain`/the Web UI don't
  expose `--llm-provider` this milestone — the `llm/` package itself
  is fully general (any `ComposedAnswer` from any source), so wiring
  it into more call sites is straightforward future work, not an
  architectural gap.
- **No live provider call was ever made** — neither SDK is installed
  and no API key is configured in this environment; every "success"
  path is proven with a fake `LLMProvider`, and every provider-specific
  path exercises the real "unavailable" branch. A real end-to-end
  OpenAI/Anthropic call was out of scope here (no credentials, no
  network call without explicit user request) and remains unverified
  against the actual live APIs.
- **`model`/timeout aren't CLI flags** — env-var/default-driven for
  now; the underlying `LLMConfig` already supports them for a future
  caller (Web UI, a config file) to expose.

## Future Extension Points

- Wire `--llm-provider` into `search`/`explain`/interactive REPL/Web
  UI, all trivial given `LLMAdapter` takes only a `ComposedAnswer`.
- A local-model provider (e.g. via an OpenAI-compatible local server)
  would slot in as a third `providers/` module with no changes to
  `adapter.py`.
- Streaming output, if a future CLI/Web surface wants incremental
  rendering — `LLMProvider.generate()` would need a streaming variant,
  additive to the existing protocol.

## Roadmap

```
✅ M001-M018 — OCOM Reader MVP + Repository Independence + Retrieval Evolution + Extensibility + Web UI (frozen)
✅ M019 Optional LLM Layer — this document
⬜ M020 Product Release
```
