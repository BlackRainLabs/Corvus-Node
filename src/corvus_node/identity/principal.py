"""Identity principal for Node RBAC.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    OPERATOR = "operator"
    USER = "user"


class Zone(StrEnum):
    CONSOLE = "console"
    LOCAL_GUI = "local_gui"
    CHANNEL = "channel"


@dataclass(frozen=True)
class Principal:
    """Who is speaking to this Node. Gateway maps social ids onto this later."""

    issuer: str
    subject: str
    role: Role = Role.USER
    zone: Zone = Zone.CHANNEL

    @property
    def id(self) -> str:
        return f"{self.issuer}:{self.subject}"

    def is_operator(self) -> bool:
        return self.role == Role.OPERATOR


def operator_principal() -> Principal:
    return Principal(
        issuer="local",
        subject="operator",
        role=Role.OPERATOR,
        zone=Zone.CONSOLE,
    )
