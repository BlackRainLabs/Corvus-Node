"""Operator control protocol (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

import pytest

from corvus_node.node.control import ControlClient, ControlError, decode_frame, encode_frame


def test_encode_decode_roundtrip() -> None:
    raw = encode_frame("status", {"pid": 1})
    frame = decode_frame(raw)
    assert frame["type"] == "status"
    assert frame["payload"] == {"pid": 1}


def test_decode_rejects_missing_type() -> None:
    with pytest.raises(ControlError, match="type"):
        decode_frame(b'{"payload": {}}\n')


def test_decode_rejects_non_object_payload() -> None:
    with pytest.raises(ControlError, match="payload"):
        decode_frame(b'{"type": "status", "payload": []}\n')


def test_status_rpc(fake_node: object) -> None:
    with ControlClient() as client:
        frame = client.rpc("status")
    assert frame["type"] == "status_ok"
    assert frame["payload"]["vm_instance_id"] == "vmtest"


def test_chat_user_agent_rpc(fake_node: object) -> None:
    with ControlClient() as client:
        client.send("chat_attach")
        assert client.read()["type"] == "waiting"
        client.send("user", {"text": "hello"})
        recv = client.read()
        assert recv["type"] == "agent"
        assert recv["payload"]["text"] == "reply:hello"
        assert client.read()["type"] == "waiting"


def test_client_missing_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path / "empty"))
    with pytest.raises(ControlError, match="not running"):
        ControlClient().connect()
