"""Adapter contract.

An Adapter is the only layer allowed to know about a specific source
(documentation, GitHub, a CRM, Jira, a BI tool, a payment system, ...).
It yields raw, source-shaped records — never OCOMObject instances.
Turning raw records into OCOMObject is the Normalizer's job, so the
core never has to change when a new source is added.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class Adapter(ABC):
    """Retrieves raw records from one external source."""

    @abstractmethod
    def fetch(self) -> Iterable[Any]:
        """Yield raw, source-shaped records."""
        raise NotImplementedError
