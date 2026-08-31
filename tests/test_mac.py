"""Hop HMAC tests.

Organization: Black Rain Labs
Division: Research & Development Division
"""

import pytest

from corvus_node.protocol.mac import HopMac, MacError, new_session_key
from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass


def _msg(type_: str = "llm_request") -> Envelope:
    return Envelope(
        source_engine=EngineId.ENGINE3,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type=type_,
        payload={"messages": [{"role": "user", "content": "hi"}]},
    )


def test_sign_and_verify() -> None:
    key = new_session_key()
    sender = HopMac(key)
    receiver = HopMac(key)
    signed = sender.sign(_msg())
    assert signed.mac
    assert signed.payload_sha256
    receiver.verify(signed)


def test_tamper_fails() -> None:
    key = new_session_key()
    sender = HopMac(key)
    receiver = HopMac(key)
    signed = sender.sign(_msg())
    tampered = signed.model_copy(
        update={"payload": {"messages": [{"role": "user", "content": "no"}]}}
    )
    with pytest.raises(MacError, match="mac_fail"):
        receiver.verify(tampered)


def test_replay_fails() -> None:
    key = new_session_key()
    sender = HopMac(key)
    receiver = HopMac(key)
    signed = sender.sign(_msg())
    receiver.verify(signed)
    with pytest.raises(MacError, match="replay"):
        receiver.verify(signed)


def test_seq_gap_fails() -> None:
    key = new_session_key()
    sender = HopMac(key)
    receiver = HopMac(key)
    first = sender.sign(_msg())
    sender.sign(_msg())
    third = sender.sign(_msg())
    receiver.verify(first)
    with pytest.raises(MacError, match="seq_gap"):
        receiver.verify(third)
