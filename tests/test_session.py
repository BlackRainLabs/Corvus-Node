"""NodeSession MAC, elevate, and audit tests (socketpair — not corvus-node run).

Organization: Black Rain Labs
Division: Research & Development Division
"""

import asyncio
import socket
from pathlib import Path

from corvus_node.identity.principal import Principal, Role, Zone
from corvus_node.node.session import LaunchConfig, NodeSession
from corvus_node.protocol.codec import encode_message
from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass
from corvus_node.runtime.turn import GuestTurn
from corvus_node.runtime.wire import Wire

from .harness import _streams_from_sock, run_paired_turn


async def _pair(
    config: LaunchConfig,
) -> tuple[NodeSession, Wire, asyncio.Task[str], asyncio.StreamWriter]:
    left, right = socket.socketpair()
    session = NodeSession(config)
    host_reader, host_writer = await _streams_from_sock(left)
    guest_reader, guest_writer = await _streams_from_sock(right)
    host_task = asyncio.create_task(session.serve(host_reader, host_writer))
    wire = Wire(guest_reader, guest_writer)
    return session, wire, host_task, guest_writer


async def test_session_key_not_audited() -> None:
    _, session = await run_paired_turn("hello")
    blob = str([e.details for e in session.audit.events()])
    assert "session_key" not in blob
    assert session.mac.key_hex is not None


async def test_mac_tamper_flags_and_drops() -> None:
    config = LaunchConfig(user_text="hello")
    session, wire, host_task, _ = await _pair(config)
    await GuestTurn(wire).handshake()
    inbound = await wire.read()
    assert inbound.type == "user_query"
    signed = wire.mac.sign(
        Envelope(
            source_engine=EngineId.ENGINE3,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="llm_request",
            payload={"messages": [{"role": "user", "content": "hi"}]},
        )
    )
    tampered = signed.model_copy(update={"payload": {"messages": []}})
    wire._writer.write((encode_message(tampered) + "\n").encode("utf-8"))
    await wire._writer.drain()
    await host_task
    flags = [e for e in session.audit.events() if e.event_type == "flag"]
    assert any(e.details.get("code") == "mac_fail" for e in flags)


async def test_seq_replay_flags() -> None:
    config = LaunchConfig(user_text="hello")
    session, wire, host_task, _ = await _pair(config)
    await GuestTurn(wire).handshake()
    inbound = await wire.read()
    assert inbound.type == "user_query"
    msg = Envelope(
        source_engine=EngineId.ENGINE3,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type="llm_request",
        payload={"messages": [{"role": "user", "content": "hi"}]},
    )
    signed = wire.mac.sign(msg)
    payload = (encode_message(signed) + "\n").encode("utf-8")
    wire._writer.write(payload)
    await wire._writer.drain()
    reply = await wire.read()
    assert reply.type == "llm_response"
    wire._writer.write(payload)
    await wire._writer.drain()
    await host_task
    flags = [e for e in session.audit.events() if e.event_type == "flag"]
    assert any(e.details.get("code") == "replay" for e in flags)


async def test_elevate_required_for_channel_user() -> None:
    user = Principal(issuer="telegram", subject="1", role=Role.USER, zone=Zone.CHANNEL)
    config = LaunchConfig(
        user_text="hello",
        allowed_tools=frozenset({"shell"}),
        principal=user,
    )
    session, wire, host_task, guest_writer = await _pair(config)
    await GuestTurn(wire).handshake()
    inbound = await wire.read()
    assert inbound.type == "user_query"
    resp = await wire.request(
        Envelope(
            origin_correlation_id=inbound.origin_correlation_id,
            source_engine=EngineId.ENGINE1,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="tool_call",
            payload={"name": "shell", "arguments": {}, "id": "c1"},
        ),
        claimed_engine=EngineId.ENGINE1,
    )
    assert resp.type == "tool_call_response"
    assert resp.payload.get("approved") is False
    assert resp.payload.get("code") == "ELEVATE_REQUIRED"
    elevates = [e for e in session.audit.events() if e.event_type == "elevate"]
    assert elevates
    assert elevates[0].details.get("code") == "ELEVATE_REQUIRED"
    guest_writer.close()
    await guest_writer.wait_closed()
    await host_task


async def test_path_escape_is_flagged(tmp_path: Path) -> None:
    config = LaunchConfig(
        user_text="hello",
        allowed_tools=frozenset({"file_read"}),
        workspace_paths=(str(tmp_path),),
    )
    session, wire, host_task, guest_writer = await _pair(config)
    await GuestTurn(wire).handshake()
    inbound = await wire.read()
    assert inbound.type == "user_query"
    resp = await wire.request(
        Envelope(
            origin_correlation_id=inbound.origin_correlation_id,
            source_engine=EngineId.ENGINE1,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="tool_call",
            payload={
                "name": "file_read",
                "arguments": {"path": "../etc/passwd"},
                "id": "c1",
            },
        ),
        claimed_engine=EngineId.ENGINE1,
    )
    assert resp.type == "tool_call_response"
    assert resp.payload.get("approved") is False
    flags = [e for e in session.audit.events() if e.event_type == "flag"]
    assert any(e.details.get("code") == "path_escape" for e in flags)
    guest_writer.close()
    await guest_writer.wait_closed()
    await host_task


async def test_unbound_tool_result_is_flagged() -> None:
    config = LaunchConfig(user_text="hello")
    session, wire, host_task, guest_writer = await _pair(config)
    await GuestTurn(wire).handshake()
    inbound = await wire.read()
    assert inbound.type == "user_query"
    resp = await wire.request(
        Envelope(
            origin_correlation_id=inbound.origin_correlation_id,
            source_engine=EngineId.ENGINE1,
            destination=Destination.NODE,
            message_class=MessageClass.EVENT,
            type="tool_result",
            payload={"id": "nope", "name": "echo", "result": {"ok": True}},
        ),
        claimed_engine=EngineId.ENGINE1,
    )
    assert resp.type == "error"
    assert resp.payload.get("code") == "UNBOUND_TOOL_RESULT"
    flags = [e for e in session.audit.events() if e.event_type == "flag"]
    assert any(e.details.get("code") == "unbound_tool_result" for e in flags)
    guest_writer.close()
    await guest_writer.wait_closed()
    await host_task
