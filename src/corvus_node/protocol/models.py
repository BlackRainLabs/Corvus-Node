"""Message envelope for Corvus-Node.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EngineId(StrEnum):
    LOOP = "loop"
    ENGINE1 = "engine1"
    ENGINE2 = "engine2"
    ENGINE3 = "engine3"
    ENGINE4 = "engine4"
    NODE = "node"


class MessageClass(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    SYSTEM = "system"


class Destination(StrEnum):
    NODE = "node"
    ENGINE = "engine"
    LOOP = "loop"


class Envelope(BaseModel):
    """One hop on the Node (host) ↔ engine (guest) vsock."""

    model_config = ConfigDict(use_enum_values=True)

    version: Literal["1.1"] = "1.1"
    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    origin_correlation_id: UUID | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_engine: EngineId
    destination: Destination
    dest_target: str = ""
    message_class: MessageClass
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    seq: int = 0
    payload_sha256: str = ""
    mac: str = ""


ALLOWED_OUTBOUND: dict[EngineId, frozenset[str]] = {
    EngineId.LOOP: frozenset({"handshake"}),
    EngineId.ENGINE1: frozenset({"tool_call", "tool_result"}),
    EngineId.ENGINE2: frozenset({"user_query", "agent_response"}),
    EngineId.ENGINE3: frozenset({"llm_request"}),
    EngineId.ENGINE4: frozenset({"memory:query", "memory:write"}),
    EngineId.NODE: frozenset(),
}
