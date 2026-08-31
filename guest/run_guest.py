"""Guest entry: 4-engine turn over vsock to host Node.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket

from corvus_node.runtime.turn import GuestTurn
from corvus_node.runtime.wire import Wire

DEFAULT_HOST_CID = 2
DEFAULT_PORT = 4040


def _vsock_connect(cid: int, port: int) -> socket.socket:
    if not hasattr(socket, "AF_VSOCK"):
        raise RuntimeError("AF_VSOCK is required in the guest")
    sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    sock.connect((cid, port))
    return sock


async def _run(cid: int, port: int, tools: frozenset[str]) -> str:
    sock = _vsock_connect(cid, port)
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    wire = Wire(reader, writer)
    return await GuestTurn(wire, tools=tools).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corvus-Node guest (inside the microVM)")
    parser.add_argument(
        "--cid",
        type=int,
        default=int(os.environ.get("CORVUS_NODE_HOST_CID", DEFAULT_HOST_CID)),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CORVUS_NODE_VSOCK_PORT", DEFAULT_PORT)),
    )
    parser.add_argument("--tools", default=os.environ.get("CORVUS_NODE_TOOLS", ""))
    args = parser.parse_args(argv)
    tools = frozenset(t.strip() for t in args.tools.split(",") if t.strip())
    text = asyncio.run(_run(args.cid, args.port, tools))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
