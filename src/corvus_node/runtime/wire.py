"""NDJSON request/response over an asyncio stream (vsock in production).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio

from corvus_node.protocol.codec import decode_line, encode_message
from corvus_node.protocol.mac import HopMac
from corvus_node.protocol.models import EngineId, Envelope
from corvus_node.runtime.validator import validate_outbound


class Wire:
    """Guest-side vsock client: validate, MAC, send to Node, wait for one reply."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        mac: HopMac | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._lock = asyncio.Lock()
        self.mac = mac or HopMac()

    def set_session_key(self, key_hex: str) -> None:
        self.mac.set_key(key_hex)

    def set_bind(self, *, vm_instance_id: str, guest_cid: int) -> None:
        self.mac.set_bind(vm_instance_id=vm_instance_id, guest_cid=guest_cid)

    async def request(self, message: Envelope, *, claimed_engine: EngineId) -> Envelope:
        validate_outbound(message, claimed_engine=claimed_engine)
        async with self._lock:
            signed = self.mac.sign(message)
            payload = encode_message(signed) + "\n"
            self._writer.write(payload.encode("utf-8"))
            await self._writer.drain()
            line = await self._reader.readline()
            if not line:
                raise ConnectionError("node closed the vsock")
            reply = decode_line(line.decode("utf-8"))
            self.mac.verify(reply)
            return reply

    async def read(self) -> Envelope:
        line = await self._reader.readline()
        if not line:
            raise ConnectionError("node closed the vsock")
        message = decode_line(line.decode("utf-8"))
        self.mac.verify(message)
        return message
