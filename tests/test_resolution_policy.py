"""ResolutionPolicy v0.1.

Standalone: no Storage, no IdentityResolver, no OCOMObject involved —
just the fold rules from
docs/architecture/OCOM-Runtime-v0.2-Resolution-Evidence-Design.md §3-5
applied to already-produced comparison results.
"""

from __future__ import annotations

from ocom_reader.runtime.resolution.policy import ResolutionCandidate, ResolutionPolicy


def test_single_match_is_accepted() -> None:
    candidates = [ResolutionCandidate(object_id="obj-a", decision="MATCH", confidence="High")]

    outcome = ResolutionPolicy().decide(candidates)

    assert outcome.result == "ACCEPT"
    assert outcome.accepted_object_id == "obj-a"
    assert outcome.warnings == []


def test_multiple_matches_are_uncertain() -> None:
    candidates = [
        ResolutionCandidate(object_id="obj-a", decision="MATCH", confidence="High"),
        ResolutionCandidate(object_id="obj-b", decision="MATCH", confidence="High"),
    ]

    outcome = ResolutionPolicy().decide(candidates)

    assert outcome.result == "UNCERTAIN"
    assert outcome.reason == "multiple_matches"
    assert outcome.accepted_object_id is None


def test_match_with_unrelated_uncertain_is_still_accepted_but_flagged() -> None:
    candidates = [
        ResolutionCandidate(object_id="obj-a", decision="MATCH", confidence="High"),
        ResolutionCandidate(object_id="obj-b", decision="UNCERTAIN", confidence="Low"),
    ]

    outcome = ResolutionPolicy().decide(candidates)

    assert outcome.result == "ACCEPT"
    assert outcome.accepted_object_id == "obj-a"
    assert outcome.warnings == ["uncertain_candidate_present"]


def test_only_uncertain_candidates_stay_uncertain() -> None:
    candidates = [
        ResolutionCandidate(object_id="obj-a", decision="UNCERTAIN", confidence="Low"),
        ResolutionCandidate(object_id="obj-b", decision="UNCERTAIN", confidence="Low"),
    ]

    outcome = ResolutionPolicy().decide(candidates)

    assert outcome.result == "UNCERTAIN"
    assert outcome.accepted_object_id is None


def test_new_with_no_competing_candidates() -> None:
    candidates = [ResolutionCandidate(object_id="obj-a", decision="NEW", confidence="Verified")]

    outcome = ResolutionPolicy().decide(candidates)

    assert outcome.result == "NEW"
    assert outcome.accepted_object_id is None


def test_no_candidates_at_all_defaults_to_new() -> None:
    """Not one of the task's numbered scenarios, but the natural
    extension of Test 5: storage had nothing to compare against at
    all, which is exactly what runtime/pipeline.py's
    _resolve_against_storage() already special-cases before ever
    calling IdentityResolver."""
    outcome = ResolutionPolicy().decide([])

    assert outcome.result == "NEW"
