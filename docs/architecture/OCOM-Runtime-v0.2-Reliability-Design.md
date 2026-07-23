# OCOM Runtime v0.2 — Reliability Hardening Design

**Status:** Draft — design only, nothing in this document has been implemented.
**Date:** 2026-07-23
**Builds on:** [MILESTONE-004](MILESTONE-004.md) (`commit 20a2196`), [Architecture-Status-v0.1](Architecture-Status-v0.1.md), [ADR-003](ADR-003-metadata-semantic-boundary.md), [ADR-005](ADR-005-identity-resolution-signal-model.md)
**Not touched by this document:** `core/`, `interfaces/`, `storage/`, `agent/`, `identity/`, `intelligence/`, `runtime/`. No code, no new dependencies, no new runtime components are created here — only the design those future changes would follow.

## 1. Purpose

[MILESTONE-004](MILESTONE-004.md) proved the full `Document → Answer`
loop executes, and in doing so produced four concrete, reproduced
reliability findings — not speculation, things that actually happened
when real components were chained together for the first time. This
document is the architectural response to those four findings. It
decides *what the fix should be shaped like*, not *the fix itself* —
consistent with how every prior layer in this project (Identity
Resolution, Object Intelligence, Classification Engine) was designed
before it was built.

OCOM Runtime v0.2 is the name for the version of the runtime where
these four gaps have an architectural answer, whether or not the code
implementing that answer exists yet.

## 2. Current Runtime Limitations

Sourced only from [MILESTONE-004](MILESTONE-004.md#new-assumptions-discovered) — nothing here is a new complaint:

1. **Registry's keyword search leaks Python dict internals.**
   `ObjectRegistry._searchable_text()` stringifies raw `metadata`
   dicts. A query containing the literal word `"concept"` matched an
   object purely because `str({"concept": "Affiliate Manager"})`
   contains the substring `"concept"` — the dict *key name*, not any
   actual content.
2. **Short and common tokens produce false positives.** A query for
   `"Payment Manager"` matched an unrelated `"Affiliate Manager"`
   object via the terms `"a"` and `"is"` — substrings of almost
   anything.
3. **The pairwise-to-storage fold rule was invented during
   implementation, never architecturally decided.** `runtime/pipeline.
   py`'s `_resolve_against_storage()` picks "first `MATCH` wins, else
   first `UNCERTAIN` wins, else `NEW`" with no stated reason to prefer
   that over any other rule, and no handling at all for *multiple*
   simultaneous `MATCH` candidates (MILESTONE-004 never actually
   exercised that case).
4. **`Answer.sources` mixes human-facing references with internal
   provenance pointers.** Once `ClassificationEngine` enriches an
   object, its derived `Evidence.reference` points at an *upstream
   `Evidence.identity`* (e.g. `evidence:fsdoc:35cc1254...`), not a file
   path — and that string ends up in the same flat list as
   `AffiliateManager.md`, with nothing distinguishing the two to a
   reader.

## 3. Query Normalization Design

```
Raw Query
    |
    v
Query Normalizer
    |
    v
Normalized Query
    |
    v
Registry Search
```

**What `QueryNormalizer` owns:**

- Case-folding.
- Punctuation stripping (the same `[^a-z0-9]+` → space substitution
  already used identically in `identity/resolver.py` and
  `intelligence/classification.py` — reusing an existing, proven
  pattern, not inventing a new one).
- Stopword removal, from a small, fixed, English function-word list
  (`"a"`, `"an"`, `"the"`, `"is"`, `"are"`, `"what"`, `"of"`, `"in"`,
  `"on"`, and similarly short grammatical words) — this is the direct
  fix for Limitation 2.
- A minimum token length filter, to catch short tokens a stopword list
  might miss (the two together are more robust than either alone — a
  bare length cutoff would drop legitimate short words; a bare
  stopword list can't anticipate every short word).

**What `QueryNormalizer` must NOT own:**

- **Meaning.** No synonym expansion, no stemming, no lemmatization —
  that is interpretation, and interpretation is explicitly excluded
  from this design (§9). `QueryNormalizer` is a mechanical filter, not
  a language model.
- **Identity comparison.** It has nothing to do with
  `IdentityResolver`'s own internal `_tokenize()`. These are two
  independent tokenizers serving two independent purposes — see below.
- **Object-side representation.** It normalizes the *query string*
  only. Fixing what a stored object exposes for matching is a
  different problem, solved separately in §4 — conflating the two
  would mean one component owning both sides of a comparison it isn't
  positioned to reason about correctly.
- **Scoring or ranking.** `QueryNormalizer` produces a cleaned query;
  it does not decide which results matter more.

**Does normalization affect identity resolution, or only search?**
**Only search.** `IdentityResolver` never sees a user query — it
compares two `OCOMObject`s (`identity/resolver.py`,
`resolve(candidate, existing)`). `QueryNormalizer` sits exclusively on
the `ask()` path, between a raw query string and
`Registry.find_candidates()`. Nothing about this design touches how
`metadata["identity"]` values are tokenized for identity comparison —
that remains `IdentityResolver`'s own concern, unchanged, per this
task's constraint not to modify `identity/`.

**Token rules, concretely** (mechanism, not tuned numbers — see §8 for
why the exact stopword list and length cutoff are not fixed here):

1. Lowercase the raw query.
2. Replace all non-alphanumeric runs with a single space.
3. Split on whitespace.
4. Drop tokens shorter than a minimum length.
5. Drop tokens present in the stopword list.
6. What remains is the `Normalized Query` handed to `Registry Search`.

## 4. Registry Search Boundary

**Searchable**, per the task's own example, made precise:

- `object_type` (unchanged, already flat)
- `classification` (unchanged, already flat)
- `metadata["identity"]` **values** (not key names — `"Affiliate
  Manager"`, not `"concept"`)
- `metadata["attributes"]` **values that are themselves meaningful
  labels** — `domain`, `category`, `type` values specifically, not the
  whole structured record (which also contains `evidence`,
  `confidence`, `timestamp` — none of which are searchable, see below)

**Non-searchable:**

- `metadata["technical"]` entirely (filenames, sizes, encodings —
  descriptive, never comparison-worthy, per
  [ADR-003](ADR-003-metadata-semantic-boundary.md))
- Timestamps, anywhere they appear
- Provenance identifiers (`Evidence.identity`, and any
  `metadata["attributes"][...]["evidence"]` reference lists)
- Internal references — including the exact string that caused
  Limitation 1: dict **key names** are never searchable, only the
  **values** under known, named fields.

**Where does this policy live? Options, per the task:**

- **A — Inside `Registry`.** What exists today
  (`_searchable_text()`), already proven insufficient (Limitations 1
  and 2 both originate here).
- **B — A dedicated Search Policy component**, taking an `OCOMObject`
  and producing a computed, ephemeral set of searchable strings — a
  read-only projection, nothing persisted, nothing added to the
  object.
- **C — The object exposes its own searchable representation** (e.g. a
  method on `OCOMObject` itself).

**Decision: B.** **C is not merely worse, it is incompatible with this
task's own constraints** — `OCOMObject` (`core/object.py`) is
explicitly frozen; giving it a new method is a Core change regardless
of how small, and is ruled out before any comparison on merits is
needed. Between A and B: **A is what already exists and already
failed** — keeping the policy inside `Registry` means any future
consumer that also needs a clean, key-name-free view of an object
(most plausibly a real `Query Engine`, [already named as Planned in
Architecture-Status-v0.1](Architecture-Status-v0.1.md#planned), or a
future `IdentityResolver v0.2` scoring pass) would either duplicate
`Registry`'s logic or depend on `Registry` for something that isn't
really Registry's job. This is the same reasoning
[ADR-003](ADR-003-metadata-semantic-boundary.md) already used to
prefer shared namespace conventions over consumer-specific whitelists:
one shared, reusable projection, defined once, is what keeps this from
becoming a repeating problem. **B — a dedicated Search Policy
component** — is the decision.

This component is *designed*, not implemented, by this document (per
this task's constraint against creating new runtime components); §10
names where it would plug in.

## 5. Resolution Decision Policy

The scenario posed: three candidates come back from comparing one new
object against everything already in `Storage` of the same
`object_type` — `A: MATCH/High`, `B: MATCH/Medium`, `C: UNCERTAIN`.
What happens?

**A precondition worth stating plainly first:** today's actual
`IdentityResolver` cannot produce this exact scenario — `MATCH`
always carries confidence `"High"` (hardcoded, not graded;
`identity/resolver.py`). Two simultaneous `MATCH`es today would be
`MATCH/High` and `MATCH/High` — a true tie, not a rankable pair. This
design covers both today's reality (ties only) and the graded case
`IdentityResolver v0.2` ([ADR-005](ADR-005-identity-resolution-signal-model.md))
might eventually produce, without assuming the second exists yet.

**Decision: multiple simultaneous `MATCH` candidates are never
auto-ranked and picked — multiplicity itself is treated as ambiguity,
downgraded to the same outcome as `UNCERTAIN`, regardless of
confidence differences.**

Reasoning, directly from the task's own stated principle — **a wrong
merge is more expensive than a duplicate:** if two *different*,
already-stored objects both independently score as a `MATCH` against
one new candidate, that is not really information about which of the
two is "more correct" — it is evidence that `Storage` itself already
contains two objects close enough to be confused for each other. Merging
into "the higher-confidence one" resolves the symptom (one merge
happens) while hiding the actual problem (an unresolved near-duplicate
already existed). A rule that picks a winner by confidence would
launder that pre-existing ambiguity into a confident-looking, silent
decision — exactly the failure mode this whole project has repeatedly
refused to accept (MILESTONE-003's false `MATCH`, [ADR-005](ADR-005-identity-resolution-signal-model.md)'s
evidence-gating, this same document's own §2 Limitation 3).

**Concretely, the fold rule (replacing today's ad hoc "first `MATCH`
wins"):**

```
matches    = [d for d in decisions if d.result == "MATCH"]
uncertains = [d for d in decisions if d.result == "UNCERTAIN"]

if len(matches) == 1:
    → MATCH, merge permitted, against that one object
elif len(matches) > 1:
    → UNCERTAIN (ambiguous — multiple existing objects matched), no merge
elif uncertains:
    → UNCERTAIN, no merge
else:
    → NEW
```

- **Ranking:** none, by design — see above. There is no "pick the best
  `MATCH`" step.
- **Tie handling:** a tie among `MATCH`es is the *specific* case that
  routes to `UNCERTAIN` — not a special case requiring its own rule,
  just the natural result of "more than one `MATCH`" always doing so.
- **Ambiguity rules:** `UNCERTAIN` — from a single ambiguous candidate
  or from multiple conflicting `MATCH`es alike — never merges
  automatically. Both cases currently collapse to the same outcome;
  whether they should be distinguishable is named in §8.
- **Merge permission:** granted only when exactly one `MATCH` exists
  among all candidates compared. Every other outcome — `NEW`,
  single `UNCERTAIN`, or multiple `MATCH` — results in the candidate
  being stored under its own identity, never merged.

## 6. Evidence Presentation Architecture

```
Internal Provenance
        |
        v
Presentation Mapping
        |
        v
Human-readable Evidence
```

`core/evidence.py` is frozen — this section defines an external,
read-time transformation, never a change to what `Evidence` stores.

**What the mapping does:** for each `Evidence` on an object being
presented, decide whether its `reference` is human-facing (a real file
path, URL, or similar external pointer) or an internal pointer (per
[OCOM-Object-Intelligence-v0.1.md §5.4](OCOM-Object-Intelligence-v0.1.md#54-evidence-model-integration),
derived `Evidence` has `source` prefixed `"object-intelligence:*"` and
a `reference` that is another `Evidence.identity`, not a location).
That prefix is already the signal needed — no new field, no Core
change:

- **`source` does not start with `"object-intelligence:"`** → the
  `reference` is already human-facing (e.g. `AffiliateManager.md`).
  Presented as-is.
- **`source` starts with `"object-intelligence:*"`** → the `reference`
  is an internal pointer. The mapping resolves it: look up the
  `Evidence` on the same object whose `identity` equals this
  `reference`, and present *that* entry's human-facing location,
  labeled to show the derivation — e.g. *"Classified via
  `object-intelligence:classification-engine`, based on:
  `AffiliateManager.md`"* — rather than showing the opaque
  `evidence:fsdoc:35cc1254...` string on its own.

**What it explicitly cannot do today:** the task's own example shows
`"Section: Responsibilities"` as a target output. Nothing in the
current `Evidence` model (`reference`: a path string; `excerpt`: a text
quote) carries section-level structure. This design does not invent
that data — it is named as a real gap in §8, not quietly assumed away.
The mapping can only ever present what `Evidence` actually holds.

**Where it lives:** conceptually, a read-time step between
`EvidenceAggregator`'s output and `AnswerComposer`'s rendering — not a
replacement for either, and not proposed as code here. §10 names it as
migration impact on `agent/answer.py`, not as something built by this
document.

## 7. Stable Decisions

Treated as settled by this design, pending implementation:

- `QueryNormalizer` is a narrow, mechanical, query-side-only filter —
  no semantic interpretation, no reuse for identity comparison.
- Registry Search Policy lives in a dedicated component (§4, Option
  B) — not inside `Registry`, not on `OCOMObject`.
- The searchable/non-searchable boundary (§4): namespace *values*,
  never dict *key names*; `technical`, timestamps, and provenance IDs
  are permanently non-searchable.
- Multiple simultaneous `MATCH` candidates are always ambiguity, never
  auto-ranked — merge permission requires exactly one `MATCH`.
- Evidence presentation is a read-time, external mapping keyed off
  `Evidence.source`'s existing naming convention — never a mutation of
  stored `Evidence`.

## 8. Open Questions

1. **The exact stopword list and minimum token length** (§3) are
   deliberately not numbered here — picking specific values without
   real query data to validate them against would be exactly the kind
   of guess-dressed-as-decision this project has repeatedly avoided
   (most recently [ADR-005](ADR-005-identity-resolution-signal-model.md)'s
   deferred thresholds).
2. **Where `QueryNormalizer` and the Search Policy component should
   live in the package structure** — inside `agent/`, or their own
   small package — not decided.
3. **Should the Search Policy component's output also feed a future
   `IdentityResolver v0.2`'s scoring**, making it a shared projection
   across query-time and identity-time, or should the two stay
   independent? Named, not decided.
4. **Should `UNCERTAIN` from a single ambiguous candidate be
   distinguishable from `UNCERTAIN` from multiple conflicting
   `MATCH`es** (§5)? They currently collapse to one outcome; whether
   that loses information worth keeping is untested.
5. **Does `IdentityDecision` (`identity/decision.py`) eventually need
   to carry more than one `matched_object_id`** — e.g. a list of the
   candidates that made a decision ambiguous — to make §5's policy
   fully auditable? This is a real, named future need, not designed
   here: `identity/` is frozen for this task, and changing
   `IdentityDecision`'s shape is exactly the kind of thing that needs
   its own ADR, not a side effect of this document.
6. **Can Evidence Presentation ever reach section-level granularity**
   (§6), or does that require `Evidence`/`excerpt` to carry more
   structure than they do today? Not solved — named as a real limit,
   not deferred silently.

## 9. Non-Goals

Explicitly excluded, per the task:

- Embeddings
- Vector database
- New LLM agents — nothing in this design introduces a new LLM call;
  `QueryNormalizer` and the Search Policy component are both purely
  mechanical
- Any change to `OCOMObject`, `Evidence`, or any file under
  `interfaces/`

Also excluded, consistent with this project's standing discipline:

- Any change to `IdentityResolver`'s actual scoring formula or
  thresholds — this document defines a policy for folding its outputs
  together, not a change to what it outputs
- Numeric tuning of stopwords/token-length cutoffs (§8)
- A general-purpose presentation/templating system — the Evidence
  Presentation Mapping (§6) does exactly one thing (resolve internal
  references to their human-facing origin), not a generic rendering
  framework

## 10. Migration Impact

Which existing components would change if this design is implemented
— named so a future task doesn't have to rediscover the list, nothing
here performed:

- **`agent/registry.py`** — `_searchable_text()` would be replaced by
  a call to the new Search Policy component (§4), instead of
  `str(value) for value in obj.metadata.values()`.
- **`runtime/pipeline.py`** — `_resolve_against_storage()`'s fold logic
  would be replaced by §5's policy (multiple-`MATCH` → `UNCERTAIN`,
  not "first wins"). This is the most concrete, direct change this
  design implies: MILESTONE-004 already flagged the current fold as
  unvalidated, and this document is that validation's answer.
- **The `ask()` entry point** (`runtime/pipeline.py`) — would gain a
  `QueryNormalizer` step before calling `Registry.find_candidates()`.
- **`agent/answer.py`** — would gain the Evidence Presentation Mapping
  (§6) as a step before or inside `AnswerComposer.compose()`, so
  `Answer.sources`/`Answer.text` stop mixing file paths with synthetic
  evidence-identity strings.
- **`identity/decision.py`** — **not changed by this design**, but
  §8's Open Question 5 names a plausible future need
  (`IdentityDecision` carrying more than one candidate identity for
  the multi-`MATCH` case). Left for its own future ADR.

None of the above is implemented by this document.
