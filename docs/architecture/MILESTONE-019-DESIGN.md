# MILESTONE-019: Optional LLM Layer — Design

**Date:** 2026-07-24
**Status:** Design — proceeding to implementation.
**Builds on:** [MILESTONE-018](MILESTONE-018.md), [MILESTONE-009-010](MILESTONE-009-010.md)

## Objective

Optional natural-language generation with zero changes to the
deterministic execution path. `Reader`, `Composer`, `Retrieval`,
`Registry`, and `Indexer` are unchanged, unimported-from, and
untouched by anything in this milestone — the LLM sits strictly after
`ComposedAnswer`.

## The One Rule

`LLMAdapter` never receives a `Reader`, `RetrievalEngine`,
`KnowledgeRegistry`, or `RepositoryIndex` — only an already-built
`ComposedAnswer`. It cannot retrieve, search, rank, or invent evidence
because it has no handle to anything that could do those things. This
is the same structural guarantee M017 gave the plugin layer, applied
to the LLM layer.

## Package Structure

```
llm/
    __init__.py
    models.py       LLMProviderName, LLMConfig, LLMResult
    protocol.py       LLMProvider (Protocol) — generate(prompt, timeout) -> str
    exceptions.py      LLMProviderUnavailableError
    adapter.py          LLMAdapter — prompt building, hard timeout, fallback, never raises
    providers/
        __init__.py
        openai.py        OpenAIProvider — lazy-imports `openai`
        anthropic.py      AnthropicProvider — lazy-imports `anthropic`
```

## Provider-Independence: `Reader` Depends Only on the Protocol

`LLMAdapter.enhance(composed_answer) -> LLMResult` is the only method
anything outside `llm/` ever calls. `Reader` itself gains **no** new
parameter, method, or import — it is verified unchanged via
`git diff --stat` at the end, the same check every prior milestone
ran. Callers (CLI, Web API) that want natural-language output
construct their own `LLMAdapter` and call it *after* `reader.answer()`,
never instead of it.

## No Provider Required for Installation

`pyproject.toml`'s base dependencies stay `pydantic` alone.
`openai`/`anthropic` are added as `[project.optional-dependencies]`
extras (`pip install ocom-reader[openai]`) — installable, never
required. Each provider module does its SDK import *inside*
`__init__`, not at module load time, so importing `ocom_reader.llm`
itself never fails even with neither SDK installed — verified
directly in this environment, where neither package is installed
(confirmed: `ModuleNotFoundError` for both `openai` and `anthropic`),
making "provider unavailable" a real, not simulated, test scenario.

## Configuration

```python
class LLMProviderName(str, Enum):
    DISABLED = "disabled"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class LLMConfig(BaseModel):
    provider: LLMProviderName = LLMProviderName.DISABLED
    model: Optional[str] = None
    timeout_seconds: float = 10.0
```

**No `api_key` field.** Keys are read *only* from environment
variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) inside each provider,
never accepted as a CLI argument (would leak into shell history and
process listings) and never part of any persisted config —
`LLMConfig` is never written to `.ocom/`, `workspace.json`, or
anywhere else. This is a deliberate security decision, not an
oversight, named explicitly per the task's own "security
considerations" documentation requirement.

## Fallback and Timeout — Enforced by the Adapter, Not Trusted to the SDK

```python
def enhance(self, answer: ComposedAnswer) -> LLMResult:
    if self._provider is None:
        return LLMResult(text=None, used_provider=self._config.provider, fallback_reason=self._unavailable_reason)
    prompt = self._build_prompt(answer)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._provider.generate, prompt, timeout=self._config.timeout_seconds)
            text = future.result(timeout=self._config.timeout_seconds)
        return LLMResult(text=text, used_provider=self._config.provider)
    except FuturesTimeoutError:
        return LLMResult(text=None, used_provider=self._config.provider, fallback_reason="timeout")
    except Exception as exc:
        return LLMResult(text=None, used_provider=self._config.provider, fallback_reason=str(exc))
```

A hard wall-clock timeout via `ThreadPoolExecutor.result(timeout=...)`
wraps every provider call — enforced by the adapter itself, not
assumed from whatever timeout behavior a given SDK claims to
implement. `enhance()` **never raises** — every failure mode (no
provider configured, SDK not installed, network error, API error,
timeout) produces an `LLMResult` with `text=None` and a
`fallback_reason`, never an exception the caller has to catch. This is
what "failures must never interrupt the normal Reader pipeline" means
structurally, not just as an intention.

## Prompt Construction — Bounded to What `ComposedAnswer` Already Contains

The prompt is built from `answer.query`, `answer.answer`,
`answer.evidence` (title/path/reasons only — the same fields the CLI
already renders), `answer.related_documents`, and `answer.reading_order`.
Nothing else — no raw file content (never indexed to begin with, per
M006), no repository paths beyond what's already in evidence, no
instruction the LLM could interpret as "go find more." The system
prompt explicitly tells the model its job is rewriting/summarizing
*this data*, not sourcing new information — never a guarantee against
model behavior, but the honest limit of what this milestone can
enforce structurally (the actual non-negotiable guarantee is that
`ComposedAnswer` itself, and everything Reader already computed, is
returned unchanged alongside whatever text the LLM produces).

## What Comes Back

```python
class LLMResult(BaseModel):
    text: Optional[str]
    used_provider: LLMProviderName
    fallback_reason: Optional[str] = None
```

`LLMResult.text` is an *additional* natural-language string, never a
replacement for `ComposedAnswer`. CLI/Web output always shows the
existing deterministic sections (Answer/Evidence/Related
Documents/Reading Order) unchanged; when `text` is present, a "Natural
Language Answer" section is added on top. `answer.evidence`,
`answer.reading_order`, etc. are never mutated — `LLMAdapter.enhance()`
takes `ComposedAnswer` by value and never calls `.model_copy(update=...)`
on it or otherwise touches it.

## CLI Integration (the one call site, opt-in)

```bash
ocom-reader ask "..." --llm-provider openai
ocom-reader ask "..." --llm-provider anthropic
ocom-reader ask "..."                          # unchanged, no LLM
```

`--llm-provider` defaults to unset (disabled) — every existing test,
and every script that shells out to `ocom-reader ask`, sees
byte-identical output to before this milestone, the same "auto-plain
when not opted in" discipline M015/M016 already established.
`--llm-model`/timeout are not exposed as flags this milestone (env-var
driven defaults are enough for the CLI's own opt-in surface); the
`llm/` package itself supports them for future callers (e.g. Web UI,
a later milestone).

## Test Plan

- `llm/adapter.py` unit tests with an injected fake `LLMProvider`
  (the same "prove the mechanism with a deterministic fake, no real
  API call" discipline Phase 5's `LLMDocumentNormalizer` already
  established): success, provider raising, timeout, no provider
  configured, prompt content bounded to `ComposedAnswer` fields,
  `ComposedAnswer` never mutated.
- `llm/providers/openai.py`/`anthropic.py`: constructing a provider
  when the SDK isn't installed raises `LLMProviderUnavailableError`
  — a **real**, not simulated, test in this environment.
- CLI: `--llm-provider` unset → byte-identical output to before this
  milestone (the existing M009-010/M015 test suite, unmodified, is
  this proof); `--llm-provider openai` with no SDK installed → graceful
  fallback, deterministic sections still fully present.
- Parity: `ComposedAnswer` returned by `reader.answer()` before and
  after passing through `LLMAdapter.enhance()` is field-for-field
  identical except for the new `LLMResult` sitting alongside it (not
  inside it).
- Real-repository verification (before writing the above): run
  `ocom-reader ask ... --llm-provider openai` against this project's
  own repository and at least one other real repository, confirming
  graceful fallback end-to-end (no crash, deterministic sections
  intact, a clear fallback message).

## Security Considerations (for MILESTONE-019.md)

- API keys: environment variables only, never CLI args, never
  persisted.
- Only already-composed, already-presentation-safe data leaves the
  process toward a provider — no raw file paths beyond what's already
  in `ComposedAnswer`, no repository-wide content.
- Provider SDKs are optional installs; a base `pip install ocom-reader`
  never pulls in third-party network client code it doesn't need.
- Every provider call is time-bounded by the adapter itself.

Proceeding to implementation now.
