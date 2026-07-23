"""QueryNormalizer v0.1.

Mechanical only: lowercase, strip punctuation, tokenize, drop a small
fixed stopword list, drop tokens shorter than 2 characters. See
docs/architecture/OCOM-Runtime-v0.2-Reliability-Design.md §3.
"""

from __future__ import annotations

from ocom_reader.runtime.query.normalizer import QueryNormalizer


def test_strips_stopwords_and_punctuation() -> None:
    result = QueryNormalizer().normalize("What is a Payment Manager?")

    assert result.raw == "What is a Payment Manager?"
    assert result.tokens == ["payment", "manager"]


def test_does_not_over_extend_the_stopword_list() -> None:
    """"me" and "about" are not in the v0.1 stopword list — they must
    survive. Extending the list to remove them needs a concrete
    failing case first, not a guess that they're "probably noise"."""
    result = QueryNormalizer().normalize("Tell me about the Affiliate Manager")

    assert result.tokens == ["tell", "me", "about", "affiliate", "manager"]


def test_single_letter_tokens_are_dropped_entirely() -> None:
    result = QueryNormalizer().normalize("A B C")

    assert result.tokens == []
