"""SearchPolicy v0.1 — what part of an OCOMObject is searchable.

Implements docs/architecture/OCOM-Runtime-v0.2-Reliability-Design.md
§4's Option B decision: a dedicated component, not logic inside
`Registry` (the placeholder `agent/registry.py._searchable_text()`
that produced MILESTONE-004's Limitation 1) and not a method on
`OCOMObject` (which is frozen — Option C was ruled out for exactly
that reason).

Searchable, per that design:
  - `object_type`
  - `classification`
  - `metadata["identity"]` values
  - `metadata["attributes"]` values — but never the `evidence`,
    `confidence`, or `timestamp` keys nested inside an attribute
    record, since those are provenance bookkeeping, not content.

Never searchable:
  - dict *key names*, anywhere (the direct fix for MILESTONE-004's
    `"concept"` false-positive: only values are ever appended to the
    searchable text, keys are only ever used to decide whether to
    recurse into or skip a value)
  - `metadata["technical"]` — not read at all
  - `Evidence`/provenance identifiers, timestamps, confidence labels

Standalone: no dependency on `Registry`, `Storage`, or anything under
`runtime/query/`. Not wired into anything yet.
"""

from __future__ import annotations

from typing import Any

from ocom_reader.core.object import OCOMObject

NON_SEARCHABLE_ATTRIBUTE_KEYS = frozenset({"evidence", "confidence", "timestamp"})


def _extract_values(value: Any, exclude_keys: frozenset[str] = frozenset()) -> list[str]:
    """Recursively collect string leaves out of a value, never
    collecting a dict's key names — only what a key points at, and
    only for keys not in `exclude_keys`."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        collected: list[str] = []
        for key, sub_value in value.items():
            if key in exclude_keys:
                continue
            collected.extend(_extract_values(sub_value, exclude_keys))
        return collected
    if isinstance(value, list):
        collected = []
        for item in value:
            collected.extend(_extract_values(item, exclude_keys))
        return collected
    return []  # numbers, None, etc. are not natural-language labels


class SearchPolicy:
    def searchable_text(self, obj: OCOMObject) -> str:
        parts: list[str] = [obj.object_type, *obj.classification]

        identity_namespace = obj.metadata.get("identity")
        if isinstance(identity_namespace, dict):
            parts.extend(_extract_values(identity_namespace))

        attributes_namespace = obj.metadata.get("attributes")
        if isinstance(attributes_namespace, dict):
            parts.extend(_extract_values(attributes_namespace, NON_SEARCHABLE_ATTRIBUTE_KEYS))

        return " ".join(parts).lower()
