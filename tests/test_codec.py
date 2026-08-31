"""Codec tests.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from corvus_node.protocol.codec import decode_line, encode_message
from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass


def test_roundtrip() -> None:
    msg = Envelope(
        source_engine=EngineId.ENGINE3,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type="llm_request",
        payload={"messages": [{"role": "user", "content": "hi"}]},
    )
    again = decode_line(encode_message(msg))
    assert again.type == "llm_request"
    assert again.source_engine == EngineId.ENGINE3
    assert again.payload["messages"][0]["content"] == "hi"
