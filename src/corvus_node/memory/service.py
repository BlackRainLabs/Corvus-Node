"""Host-owned private memory for one identity.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations


class MemoryService:
    """v1: in-process private namespace. Not used on the echo slice."""

    def __init__(self) -> None:
        self._private: dict[str, str] = {}

    def write(self, key: str, value: str) -> None:
        self._private[key] = value

    def query(self, key: str) -> str | None:
        return self._private.get(key)
