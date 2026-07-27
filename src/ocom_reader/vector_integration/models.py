"""Vector Statement/Meeting models — Reader's side of
docs/contracts/vector-reader-contract.md (Vector repository, Contract Version 1.0).

Only the fields the contract actually governs are modeled here. `extra="ignore"`
on both models is the concrete implementation of the contract's "Reader must
ignore unknown fields" rule — made explicit rather than left to Pydantic's
implicit default, since this is a stated compatibility promise, not an accident
of the library. This is what lets Vector add a new optional field (as it already
did once, adding `detected_signals` in its own M04.3) without breaking Reader.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# The contract's closed, stable signal vocabulary ("Compatibility guarantees" #4).
# Reader may rely on detected_signals never containing anything outside this set —
# but must NOT assume every combination of them has already been seen; see
# signals.py's module docstring and the contract's own "detected_signals is a set
# of independent signals, not an enumeration of allowed combinations" section.
KNOWN_SIGNALS = frozenset({"metric", "question", "risk", "task", "decision"})

# The contract's closed, stable statement_kind enum (guarantee #3). Informational
# here — Reader does not reject a Statement whose statement_kind falls outside
# this set (that would violate the "ignore, don't reject" spirit of the unknown-
# fields rule); it's exposed so callers can recognize the six known values.
KNOWN_STATEMENT_KINDS = frozenset(
    {"fact", "metric", "decision_signal", "task_signal", "risk_signal", "other"}
)

# Fixed display order for Reader M02's summaries/browser/signal-view — the same
# five names as KNOWN_SIGNALS, ordered for stable, predictable output. Not a
# ranking or a precedence — just a consistent order to render in, independent
# of insertion order in any particular Statement's detected_signals list (which
# Vector itself writes alphabetically) or of frozenset iteration order (which
# is not guaranteed stable across runs).
SIGNAL_DISPLAY_ORDER = ("task", "metric", "risk", "decision", "question")


class VectorStatement(BaseModel):
    """A Vector Statement object, per the contract's "Mandatory fields" and
    "Optional fields" sections. Fields not listed in either section of the
    contract are not modeled here at all — they pass through Pydantic's
    extra="ignore" and are simply never seen by Reader, which is exactly what
    the contract asks for."""

    model_config = ConfigDict(extra="ignore")

    # --- Mandatory (contract: "Mandatory fields") ---
    id: str
    type: str
    title: str
    tenant: str
    owner: str
    status: str
    lifecycle: str
    language: str
    created: str
    updated: str
    confidence: str
    source: str
    speaker: str
    meeting_ref: str
    timestamp: str
    text: str

    # --- Optional (contract: "Optional fields") ---
    domain: str = ""
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    speaker_resolved: Optional[bool] = None
    statement_kind: Optional[str] = None
    metric_value_raw: Optional[str] = None
    # The field this milestone (Reader M01) exists to support. Absent on any
    # Statement produced before Vector's PARSER_VERSION 1.3.0, or on a
    # manually-authored one — default to an empty list, never None, so a
    # caller never needs a None-check before iterating or filtering it.
    detected_signals: list[str] = Field(default_factory=list)

    def has_signal(self, signal: str) -> bool:
        """Independent per-signal membership test — the one sanctioned way to
        query detected_signals. Never compare detected_signals as a set or
        tuple against a fixed combination; see signals.py."""
        return signal in self.detected_signals


class VectorMeeting(BaseModel):
    """The subset of a Vector Meeting object this contract governs directly —
    per the contract's "What this contract deliberately does not cover" section,
    only identity plus the two fields Reader needs to resolve Vector's M03
    idempotent-import / supersedes chain. Everything else about Meeting
    (attendees, meeting_type, ...) is out of scope for Contract v1.0 and
    intentionally not modeled here.

    EXCEPTION, added for Reader M03 (Object Navigation): `meeting_date`.
    Entity Timeline (Task 5) genuinely needs a real calendar date to sort
    mentions chronologically, and no Statement-level field the contract
    already covers can substitute for it (Statement.created is Reader's own
    ingestion date, not the meeting's date; Statement.timestamp is only an
    offset within the recording). This field is READ but is NOT part of
    Contract v1.0 — see docs/vector-integration.md and READER_M03.md for the
    explicit flag that Vector should either confirm this as a deliberate,
    documented v1.1 addition or tell Reader to get the date some other way.
    Optional, defaults to None, so a Meeting lacking it (as none currently do,
    but none of this was promised either) never breaks anything."""

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    title: str
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    source_hash: Optional[str] = None
    parser_version: Optional[str] = None
    meeting_date: Optional[str] = None  # M03 — beyond Contract v1.0, see docstring above

    def supersedes(self) -> list[str]:
        """Meeting ids this Meeting explicitly replaces, per its own
        `relationships` — the same `supersedes` relationship type Vector's own
        M03 pipeline writes. Does not say whether THIS Meeting is itself
        superseded by something newer; see loader.find_current_meetings()."""
        return [
            rel["target"]
            for rel in self.relationships
            if rel.get("type") == "supersedes" and "target" in rel
        ]


# Vector's own type prefixes for non-Statement/Meeting objects, per Vector's
# docs/identifiers-and-naming.md — used only to recognize which `type` values
# load_objects() should collect, not to parse filenames (type field is
# authoritative, same discipline as load_statements/load_meetings).
KNOWN_OBJECT_TYPES = frozenset(
    {"decision", "task", "project", "partner", "company", "employee",
     "product", "document", "risk", "issue", "evidence"}
)


class VectorObject(BaseModel):
    """Any non-Statement/Meeting Vector object (Partner, Company, Employee,
    Task, Decision, Risk, Issue, Document, Project, Product, Evidence) — for
    Reader M03's Object Navigation. Models only Vector's COMMON object
    frontmatter (Vector's docs/object-model.md), the same baseline every
    Vector object type shares, since no type-specific contract for any of
    these (a "Partner contract," an "Employee contract") exists yet.

    NOT covered by vector-reader-contract.md v1.0 at all — that contract is
    Statement-only. Reader depends here on Vector's common object model being
    stable, which is documented in Vector's own repo but not yet published as
    a versioned contract the way Statement's fields are. Flagged explicitly
    in READER_M03.md as a real gap: Vector should consider publishing a
    second contract (or extending vector-reader-contract.md) covering this
    common object shape, the same way it did for Statement."""

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    title: str
    tenant: str
    owner: str
    status: str
    lifecycle: str
    confidence: str
    source: str
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    def aliases(self) -> list[str]:
        """Registered aliases via the `alias:<form>` tags convention — the
        exact mechanism Vector's own resolve_entity()/registered_aliases()
        (ai/pipelines/ingest_transcript.py) already uses for Identity
        Resolution. Also not part of vector-reader-contract.md v1.0; same gap
        as noted on the class docstring above."""
        return [t[len("alias:"):] for t in self.tags if t.startswith("alias:")]
