"""Node-side channel adapters. Engine 2 only formats agent_response.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from typing import Protocol

from corvus_node.identity.principal import Principal, operator_principal


class ChannelAdapter(Protocol):
    """Ingress identity + text. Telegram/WhatsApp implement this later."""

    def principal(self) -> Principal: ...

    def receive_text(self) -> str: ...

    def send_text(self, text: str) -> None: ...


class LocalCliAdapter:
    """Local CLI is the firewall console: operator principal, not a social user."""

    def __init__(self, text: str) -> None:
        self._text = text

    def principal(self) -> Principal:
        return operator_principal()

    def receive_text(self) -> str:
        return self._text

    def send_text(self, text: str) -> None:
        print(text)
