# MILESTONE-006: Repository Indexer v0.1

**Date:** 2026-07-23
**Status:** Frozen — first production-ready, deterministic structural index of the OCOM Reader repository.
**Builds on:** [MILESTONE-005](MILESTONE-005.md) (Runtime v0.2 Reliability Freeze)
**Scope boundary confirmed with the requester:** "repository" means the `OCOM-Reader` git repository itself — its own `docs/`, `README.md`, and any other Markdown it contains — not the outer `OCOM-Specification-v0.1-Folders` directory, which is not a git repository and holds `.docx` specification content, not Markdown.

## Objective

Give OCOM Reader a complete, deterministic structural index of its own
documentation — what documents exist, where, what they're titled, what
they link to, and what links to them — without attempting to interpret
what any of it means. This is the knowledge foundation a future
Retrieval Engine can be built on; this milestone does not build that
engine, only the index it would read from.

## Architecture

A new, standalone subsystem, `indexer/`, deliberately independent of
the existing OCOM ingestion pipeline (`adapters/` → `normalizers/` →
`OCOMObject` → `Storage`):

```
Repository Root
      ↓
RepositoryScanner        — discover .md files, deterministically, excluding non-repo directories
      ↓
DocumentLoader            — read content + filesystem metadata (per file)
      ↓
MarkdownParser             — extract title, headings, links, preview (per file, regex-only)
      ↓
MetadataExtractor           — classify document_type, compute id + content hash (per file)
      ↓
RepositoryIndexBuilder        — assemble entries, then resolve what only
                                  the whole set can answer:
                                  internal link resolution, inbound
                                  references, duplicate detection
      ↓
RepositoryIndex                 — the queryable result
```

**Why this is not built on top of `adapters/`/`normalizers/`:** those
exist to turn one raw record into one `OCOMObject` (ADR-001) — a
pipeline this milestone's own scope explicitly excludes ("no object
extraction"). `RepositoryScanner`/`DocumentLoader` duplicate a small
amount of what `FilesystemDocumentationAdapter` already does
(discovering and reading files), but the metadata each needs diverges
completely (headings/links/document-type vs. OCOM identity/evidence),
and coupling a documentation-indexing subsystem to the OCOM object
pipeline would mean a change to either could silently break the other.
Kept independent on purpose, the same discipline already applied
between `runtime/query/`, `runtime/search/`, `runtime/resolution/`,
and `runtime/evidence/`.

## Implemented Components

| Component | Status |
|---|---|
| Repository Scanner | Implemented |
| Document Loader | Implemented |
| Markdown Parser | Implemented |
| Metadata Extractor | Implemented |
| Repository Index Builder | Implemented |

All five, plus the `RepositoryIndex`/`DocumentIndexEntry` data models,
live under `src/ocom_reader/indexer/`. 10 tests
(`tests/test_repository_indexer.py`): 9 against a synthetic, hermetic
fixture repository, plus one integration test run against the real
OCOM Reader repository — the same "prove it on real data, not just
fixtures" discipline used for `test_end_to_end_reasoning_path.py`.

## Repository Coverage

Run against the real repository at the time of this milestone:

- **20 documents indexed**, 0 invalid, 0 duplicates.
- By type: 6 ADR, 8 Architecture, 5 Milestone, 1 README.
- No "Governance" or "Lifecycle" documents exist in `OCOM-Reader` yet —
  `MetadataExtractor`'s classification rules have no case for them
  because nothing in this repository needs one yet. The categorization
  scheme itself does not preclude adding one later; it simply has
  nothing to classify into those buckets today.
- `.venv`, `__pycache__`, `.pytest_cache`, and `data/` are confirmed
  excluded — verified directly (`not any(".venv" in entry.path ...)`),
  not assumed.

## Index Structure

```python
class DocumentIndexEntry:
    id: str                          # relative path, stable and deterministic
    path: str
    title: str                       # first heading, or filename if none
    document_type: str                # "ADR" | "Milestone" | "Architecture" | "README" | "Documentation"
    last_modified: datetime
    headings: list[Heading]            # level + text, in document order
    internal_links: list[str]           # distinct targets that resolve to another indexed document
    outbound_references: list[str]       # every link found, raw, unfiltered (internal + external)
    inbound_references: list[str]         # distinct documents whose internal_links point here
    preview: str                            # first non-heading, non-blank line
    content_hash: str                        # sha256, for duplicate detection

class RepositoryIndex:
    entries: list[DocumentIndexEntry]
    invalid: list[InvalidDocument]      # path + reason, never a crash
    duplicates: list[list[str]]          # groups of ids sharing content_hash

    def get(document_id) -> Optional[DocumentIndexEntry]
    def by_type(document_type) -> list[DocumentIndexEntry]
    def all() -> list[DocumentIndexEntry]
```

## Guarantees

- **Deterministic:** two builds against the same repository state
  produce byte-identical entries (`test_build_is_deterministic_across_repeated_runs`)
  — confirmed by direct comparison, on both the synthetic fixture and
  the real repository (re-running the manual script during
  development produced identical output twice).
- **No semantic interpretation anywhere:** every extraction rule
  (heading regex, link regex, document-type classification) is fixed
  and mechanical — the same "dictionary, not inference" discipline
  already established for `intelligence/classification.py`. No new
  dependency was added; no Markdown-rendering library, no LLM.
- **Distinct occurrences vs. distinct relationships:** a document
  citing the same link twice produces one `internal_links` entry (a
  relationship exists or it doesn't) but two entries in
  `outbound_references` (every citation is still preserved,
  unfiltered) — this distinction was not obvious until tested against
  this repository's own real cross-references and is now enforced by
  a dedicated test.
- **Never crashes on bad input:** an empty file or one that fails to
  decode as UTF-8 is recorded in `invalid`, with a reason, and
  skipped — the build always completes.
- **No regressions:** all 62 pre-existing tests still pass; nothing
  outside `src/ocom_reader/indexer/` and its own test file was
  modified (`git diff --stat` on every other package is empty).

## Known Limitations

- **`internal_links` only recognizes links to other `.md` files
  within the scanned root.** A link to source code
  (e.g. `[core/object.py](../../src/ocom_reader/core/object.py)`,
  present in several real ADRs) is preserved in `outbound_references`
  but never becomes an internal link or an inbound reference — this
  index only models relationships *between documents*, not between
  documents and code.
- **No ranking, no relevance ordering.** `by_type()` and `all()`
  return entries in whatever order they were discovered (sorted by
  path) — this milestone's own scope excludes ranking algorithms.
- **Duplicate detection is exact-content only.** Two documents that
  say the same thing in different words are not detected as
  duplicates — only a byte-identical `content_hash` match is.
- **`document_type` classification has four categories and one
  fallback ("Documentation").** It was built against this
  repository's actual file-naming conventions
  (`ADR-*`, `MILESTONE-*`, `README.md`, an `architecture/` folder) —
  a differently-organized repository would need its rule table
  revisited, not because the approach is wrong, but because it was
  deliberately grounded in real data rather than guessed in the
  abstract.
- **No incremental indexing.** Every `build()` call rescans and
  reloads the entire repository from scratch — fine at this
  repository's current size (20 documents), not addressed for a
  larger one.

## Next Milestone Proposal

The Repository Indexer is a read model over this project's own
documentation, not a Retrieval Engine. A natural next step — not
started here — is a `RetrievalEngine` that answers questions like
"which document last touched topic X" using `RepositoryIndex` as its
data source, the same way `agent/registry.py` uses `Storage` — but
that is deliberately not this milestone's concern, matching its own
explicit non-goals (no answer generation, no ranking).
