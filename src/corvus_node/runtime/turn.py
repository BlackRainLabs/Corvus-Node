"""Guest turn loop.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from uuid import UUID

from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass
from corvus_node.runtime.engines import Engine1, Engine2, Engine3, Engine4
from corvus_node.runtime.wire import Wire

TOOL_SCHEMAS: dict[str, dict[str, str]] = {
    "echo": {"name": "echo", "description": "Echo text"},
    "file_read": {"name": "file_read", "description": "Read a file under /workspace"},
    "file_write": {"name": "file_write", "description": "Write a file under /workspace"},
}
HISTORY_MAX = 32


class GuestTurn:
    def __init__(self, wire: Wire, *, tools: frozenset[str] = frozenset()) -> None:
        self.wire = wire
        self.tools = tools
        self.engine1 = Engine1(wire)
        self.engine2 = Engine2(wire)
        self.engine3 = Engine3(wire)
        self.engine4 = Engine4(wire)

    async def accept_session(self) -> None:
        init = await self.wire.read()
        if init.type != "session_init":
            raise RuntimeError(f"expected session_init, got {init.type}")
        key = init.payload.get("session_key")
        if not key:
            raise RuntimeError("session_init missing host-minted key")
        self.wire.set_session_key(str(key))
        self.wire.set_bind(
            vm_instance_id=str(init.payload.get("vm_instance_id", "")),
            guest_cid=int(init.payload.get("guest_cid") or 0),
        )

    async def handshake(self) -> None:
        if self.wire.mac.key_hex is None:
            await self.accept_session()
        msg = Envelope(
            source_engine=EngineId.LOOP,
            destination=Destination.NODE,
            message_class=MessageClass.SYSTEM,
            type="handshake",
            payload={"role": "guest"},
        )
        resp = await self.wire.request(msg, claimed_engine=EngineId.LOOP)
        if resp.type != "handshake_ok":
            raise RuntimeError(f"handshake failed: {resp.type}")
        if "allowed_tools" in resp.payload:
            raw = resp.payload.get("allowed_tools") or []
            self.tools = frozenset(str(t) for t in raw)

    async def _one_turn(self, user_text: str, origin: UUID, messages: list[dict]) -> str:
        schema = [TOOL_SCHEMAS[name] for name in sorted(self.tools) if name in TOOL_SCHEMAS] or None
        messages.append({"role": "user", "content": user_text})
        self._trim(messages)
        llm_out = await self.engine3.infer(messages, origin=origin, tools_schema=schema)
        for call in llm_out.get("tool_calls") or []:
            name = str(call.get("name", ""))
            arguments = call.get("arguments") or {}
            if not isinstance(arguments, dict):
                arguments = {}
            result = await self.engine1.run_tool(
                name=name,
                arguments=arguments,
                call_id=str(call.get("id", "call")),
                origin=origin,
            )
            messages.append(
                {"role": "tool", "content": str(result), "tool_call_id": call.get("id")}
            )
        if llm_out.get("tool_calls"):
            llm_out = await self.engine3.infer(messages, origin=origin, tools_schema=None)
        text = str(llm_out.get("content") or "")
        messages.append({"role": "assistant", "content": text})
        self._trim(messages)
        await self.engine2.respond(text, origin=origin)
        return text

    def _trim(self, messages: list[dict]) -> None:
        overflow = len(messages) - HISTORY_MAX
        if overflow > 0:
            del messages[:overflow]

    async def run(self) -> str:
        await self.handshake()
        messages: list[dict] = []
        last = ""
        while True:
            inbound = await self.wire.read()
            if inbound.type == "session_end":
                return last
            if inbound.type != "user_query":
                raise RuntimeError(f"expected user_query, got {inbound.type}")
            origin: UUID = inbound.origin_correlation_id or inbound.correlation_id
            user_text = str(inbound.payload.get("text", ""))
            last = await self._one_turn(user_text, origin, messages)
