"""Guest outbound validation.

Organization: Black Rain Labs
Division: Research & Development Division
"""

import pytest

from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass
from corvus_node.runtime.validator import GuestError, validate_outbound


def test_engine3_cannot_send_tool_call() -> None:
    msg = Envelope(
        source_engine=EngineId.ENGINE3,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type="tool_call",
        payload={"name": "echo"},
    )
    with pytest.raises(GuestError, match="may not send"):
        validate_outbound(msg, claimed_engine=EngineId.ENGINE3)


def test_spoof_rejected() -> None:
    msg = Envelope(
        source_engine=EngineId.ENGINE1,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type="tool_call",
        payload={"name": "echo"},
    )
    with pytest.raises(GuestError, match="anti-spoof"):
        validate_outbound(msg, claimed_engine=EngineId.ENGINE3)
