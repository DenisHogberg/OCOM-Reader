"""MemoryStore contract.

Persists and retrieves MemoryEntry instances. Deliberately not a
subclass or generalization of Storage — Storage's abstract methods are
fixed to OCOMObject in their own signatures, so MemoryStore cannot
literally implement that interface. Storage / OCOMObject and
MemoryStore / MemoryEntry are two parallel, independent interfaces
(M021 Phase 1). Generalizing them into one shared abstraction is a
separate, future decision — its own ADR if it happens — not part of
this one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from ocom_reader.core.memory import MemoryEntry


class MemoryStore(ABC):
    @abstractmethod
    def save(self, entry: MemoryEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> Iterable[MemoryEntry]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, entry_id: str) -> None:
        raise NotImplementedError
