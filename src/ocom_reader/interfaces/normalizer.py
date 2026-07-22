"""Normalizer contract.

A Normalizer turns one raw record produced by an Adapter into one
OCOMObject. It is the only layer that translates source-specific shape
into the source-agnostic OCOM model — the boundary described in
Meta/Object.md.docx ("Objects are independent of implementation
technologies and business domains").

Because it is the boundary layer, the Normalizer is also where
`Evidence` gets attached to the resulting OCOMObject — it is the last
point that still knows which source and which raw record produced
this data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ocom_reader.core.object import OCOMObject


class Normalizer(ABC):
    """Converts a raw record into an OCOMObject."""

    @abstractmethod
    def normalize(self, raw: Any) -> OCOMObject:
        raise NotImplementedError
