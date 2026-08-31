"""Guest outbound validation before vsock to host Node.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from corvus_node.protocol.models import ALLOWED_OUTBOUND, Destination, EngineId, Envelope


class GuestError(ValueError):
    """Guest runtime rejected a message before it hit vsock."""


def validate_outbound(message: Envelope, *, claimed_engine: EngineId) -> None:
    source = EngineId(message.source_engine)
    if source != claimed_engine:
        raise GuestError("source_engine does not match caller (anti-spoof)")
    allowed = ALLOWED_OUTBOUND.get(source, frozenset())
    if message.type not in allowed:
        raise GuestError(f"engine {source} may not send {message.type}")
    if Destination(message.destination) != Destination.NODE:
        raise GuestError("outbound destination must be node")
