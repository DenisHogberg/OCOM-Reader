"""Storage contract.

Storage persists and retrieves OCOMObject instances. It has no
knowledge of adapters, normalizers, or sources — it only deals with
the source-agnostic OCOM model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from ocom_reader.core.object import OCOMObject


class Storage(ABC):
    @abstractmethod
    def save(self, obj: OCOMObject) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, identity: str) -> Optional[OCOMObject]:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> Iterable[OCOMObject]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, identity: str) -> None:
        raise NotImplementedError
