"""Test-only anonymous socket pairing. Not a product run path.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
import socket

from corvus_node.identity.principal import Principal, operator_principal
from corvus_node.node.session import LaunchConfig, NodeSession
from corvus_node.runtime.turn import GuestTurn
from corvus_node.runtime.wire import Wire


async def _streams_from_sock(
    sock: socket.socket,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


async def run_paired_chat(
    lines: list[str],
    *,
    tools: frozenset[str] = frozenset(),
    guest_tools: frozenset[str] | None = None,
    workspace_paths: tuple[str, ...] = (),
    principal: Principal | None = None,
) -> tuple[list[str], NodeSession]:
    left, right = socket.socketpair()
    prompts: asyncio.Queue[str | None] = asyncio.Queue()
    responses: asyncio.Queue[str | None] = asyncio.Queue()
    config = LaunchConfig(
        allowed_tools=tools,
        workspace_paths=workspace_paths,
        principal=principal or operator_principal(),
        once=False,
        prompts=prompts,
        responses=responses,
    )
    session = NodeSession(config)
    host_reader, host_writer = await _streams_from_sock(left)
    guest_reader, guest_writer = await _streams_from_sock(right)
    start_tools = tools if guest_tools is None else guest_tools
    collected: list[str] = []

    async def host() -> str:
        return await session.serve(host_reader, host_writer)

    async def guest() -> str:
        wire = Wire(guest_reader, guest_writer)
        return await GuestTurn(wire, tools=start_tools).run()

    async def feeder() -> None:
        for line in lines:
            await prompts.put(line)
            item = await responses.get()
            if item is None:
                break
            collected.append(item)
        await prompts.put(None)

    await asyncio.gather(host(), guest(), feeder())
    return collected, session


async def run_paired_turn(
    text: str,
    *,
    tools: frozenset[str] = frozenset(),
    guest_tools: frozenset[str] | None = None,
    workspace_paths: tuple[str, ...] = (),
    principal: Principal | None = None,
) -> tuple[str, NodeSession]:
    left, right = socket.socketpair()
    config = LaunchConfig(
        user_text=text,
        allowed_tools=tools,
        workspace_paths=workspace_paths,
        principal=principal or operator_principal(),
    )
    session = NodeSession(config)
    host_reader, host_writer = await _streams_from_sock(left)
    guest_reader, guest_writer = await _streams_from_sock(right)
    start_tools = tools if guest_tools is None else guest_tools

    async def host() -> str:
        return await session.serve(host_reader, host_writer)

    async def guest() -> str:
        wire = Wire(guest_reader, guest_writer)
        return await GuestTurn(wire, tools=start_tools).run()

    host_text, guest_text = await asyncio.gather(host(), guest())
    assert host_text == guest_text
    return guest_text, session
