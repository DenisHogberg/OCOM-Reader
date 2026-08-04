# Reader License Review — Product Readiness P01

**Status: license decision + its minimal necessary metadata.** Per the task's own
scope constraints, this covers licensing only — no CHANGELOG, CI, versioning, or
README work is included or bundled here (those remain separate Product Readiness
items, already identified in `READER_PRODUCT_READINESS.md`).

## 1. Requirements

What Reader's license actually needs to satisfy, derived from Reader's real,
checked situation — not a generic checklist:

- **Reader is a standalone project.** Its license governs Reader's own source code in
  this repository only.
- **Reader integrates with Companion but is not part of it, and does not redistribute
  Companion's code.** Checked directly: Companion's own `LICENSE`
  (`~/Downloads/Companion/LICENSE`) is proprietary, "All Rights Reserved" — a completely
  separate, private repository. Reader consumes Companion's data read-only, through a
  documented contract (`companion-reader-contract.md`); it never vendors, embeds, or
  redistributes any Companion source. **Companion's license has no bearing on Reader's
  choice, and Reader's choice has no bearing on Companion.** This is a real, checked
  non-interaction, not an assumption.
- **Reader is explicitly self-described as a *reference implementation*.** Reader's own
  `README.md`: "the first reference **Adapter** implementation of the OCOM
  architecture." This matters legally, not just descriptively: reference
  implementations of a specification are the canonical case where a **patent grant**
  has real, non-theoretical value — protecting anyone who builds an Adapter against
  the spec from a later patent claim tied to implementing it.
- **The specification Reader implements is itself Apache-2.0.** Checked directly:
  `~/Downloads/OCOM/LICENSE` is the Apache License, Version 2.0. This is real,
  concrete context for the "compatibility with anticipated growth" question below —
  not because Reader is legally required to match it, but because Reader's own stated
  ambition (a plugin/Adapter ecosystem around a specification) is exactly the same
  shape as the ecosystem OCOM's own license was chosen to support.
- **Reader already has a working plugin/extensibility architecture** (M011-M017,
  `plugins.py`) — i.e., third-party Adapters are not a hypothetical future, they are
  an already-built capability waiting for external contributors.
- **Minimize legal restriction for users and developers** — permissive, not copyleft;
  no requirement that derivative works be released under the same license; safe to
  embed in proprietary or commercial tooling without friction.

## 2. Candidate Licenses

| | MIT | Apache-2.0 | BSD-3-Clause |
|---|---|---|---|
| Commercial use | Permitted | Permitted | Permitted |
| Modification | Permitted, no obligation to document changes | Permitted, **must state changes made to modified files** | Permitted, no obligation to document changes |
| Distribution | Permitted; preserve copyright + license notice | Permitted; preserve copyright + license notice + NOTICE (if any) + stated changes | Permitted; preserve copyright + license notice |
| Patent grant | **None** — no explicit patent language at all | **Explicit, with patent-retaliation clause** — terminates the license for anyone who sues over patents reading on the licensed work | **None** — same gap as MIT |
| Simplicity | Highest — ~150 words, minimal legal apparatus | Lowest of the three — full definitions section, patent clauses, ~200 lines | High — MIT + one added non-endorsement clause |
| Community adoption | Highest overall on GitHub, especially for small Python CLI tools | High, especially for larger/corporate-backed or standards-adjacent infrastructure (Kubernetes, TensorFlow, Android) | Common, historically strong in academic/BSD-lineage software, somewhat less common than MIT for new small tools |
| Compatibility with Reader's anticipated growth | Good in the generic sense (low friction) but has no answer for the plugin-ecosystem/patent-claim scenario Reader's own architecture already anticipates | **Matches the exact shape of Reader's stated ambition**: a spec-reference implementation with a real plugin architecture inviting multiple third-party Adapter authors, aligned with the canonical OCOM specification's own license choice | Adds a non-endorsement clause with no counterpart need currently identified (no established "OCOM Reader" brand/trademark risk yet) — extra clause, no offsetting benefit for Reader specifically |

## 3. Recommendation

**Apache License, Version 2.0.**

**Why this one, not the generic-simplest choice.** The earlier product-readiness audit
(`READER_PRODUCT_READINESS.md`) flagged MIT as "the closest fit" on a generic
simplicity/popularity basis, explicitly leaving the final call open. On closer,
specifically-grounded analysis, that generic default undersells what Reader actually
is: not a small standalone utility, but a self-described reference implementation of a
specification (OCOM) that is itself Apache-2.0, with an already-built plugin
architecture explicitly anticipating multiple third-party Adapter implementations.
That is precisely the scenario Apache-2.0's patent grant and patent-retaliation clause
exist to protect — future Adapter authors building against the OCOM spec, and Reader's
own contributors, from a patent claim asserted over the specification or an
implementation of it. Aligning with the canonical specification's own license choice
also removes any future friction if code, discussion, or contributors ever need to
move between the OCOM specification repository and this one.

**Alternatives rejected, and why:**

- **MIT** — rejected specifically because it has no answer to the one requirement that
  actually differentiates Reader's situation from a generic small tool: a patent grant
  for a reference-implementation-of-a-specification with an open plugin ecosystem.
  MIT remains an excellent license in general, and would have been the reasonable
  default for a project without that specific shape — but Reader has that shape,
  checked, not assumed.
- **BSD-3-Clause** — rejected for the same patent-grant gap as MIT, plus an added
  non-endorsement clause that answers a concern (protecting an established name/brand
  from misleading endorsement claims) Reader doesn't currently have: there is no
  widely-recognized "OCOM Reader" brand or trademark at stake yet. The clause adds
  length without buying Reader anything MIT doesn't already cover.

**Consequences of this choice:**

- Low, but not zero, legal overhead for adopters: Apache-2.0 requires anyone who
  modifies Reader's files and redistributes them to state what changed — a mild
  transparency obligation MIT/BSD don't impose, reasonable for a project meant to be
  adapted by many parties, but worth naming as a real (if small) added obligation
  compared to MIT.
- Full compatibility with commercial and proprietary use — nothing about choosing
  Apache-2.0 forces any downstream user's own code to be open-sourced (it is not
  copyleft).
- No per-file license headers are being added as part of this decision — Apache-2.0
  does not require them to be legally valid (a single root `LICENSE` file granting the
  license over the whole work is sufficient); per-file headers are a common convention
  some Apache-2.0 projects adopt, not a requirement, and adding them to every existing
  source file would mean editing Reader's code, which is explicitly out of scope for
  this task.
- No `NOTICE` file is being added — Apache-2.0 permits one for aggregating
  attribution notices from bundled third-party components, but does not require one,
  and Reader vendors no third-party code that would need attributing there.

## 4. Impact

What actually needs to change once Apache-2.0 is chosen, checked against the real
current state of each item — not assumed:

| Item | Change needed? | Why / why not |
|---|---|---|
| **`LICENSE` file** | **Yes** | Doesn't exist today (confirmed in the prior audit) — this is the core deliverable of this task. |
| **`pyproject.toml`** | **Yes, minimally** | `pip show ocom-reader` currently reports a blank `License:` field. Adding the `LICENSE` file alone, without also declaring it in package metadata, would recreate the exact kind of silent inconsistency the prior audit already flagged for the version field (a file says one thing, the package's own declared metadata says nothing). The fix is narrowly scoped to the license field itself — `license = {text = "Apache-2.0"}` and the one matching classifier (`"License :: OSI Approved :: Apache Software License"`) — not the broader `authors`/`urls`/full-`classifiers` gap the prior audit also found, which remains a separate, later Phase C item. |
| **Packaging metadata** | Covered by the `pyproject.toml` change above | No separate packaging step exists yet (no PyPI publish has happened) — there is nothing else to update. |
| **README** | **No — explicitly out of scope for this task** | A short "License: Apache-2.0" line/badge would be a reasonable, near-zero-cost addition to the README, and is worth doing — but the task explicitly excludes bundling this with README work (already a separate, identified Phase B item in `READER_PRODUCT_READINESS.md`). Noted here so it isn't forgotten, not actioned now. |
| **CONTRIBUTING** | **No — doesn't exist yet** | There is no `CONTRIBUTING.md` to update (confirmed absent in the prior audit). When one is eventually written, it should state that contributions are made under the project's `LICENSE` (standard practice for an Apache-2.0 project) — a note for that future task, not an action here. |
| **GitHub Release** | **No — no release process currently exists** | No `.github/` workflows, no documented release steps exist to update (confirmed absent). The next time a release is actually cut, its notes should mention the license having been added — but there is no current release artifact to touch. |

**Net scope of the commit that follows**: exactly two files — a new `LICENSE`, and a
one-field-plus-one-classifier change to `pyproject.toml`. Nothing else.
