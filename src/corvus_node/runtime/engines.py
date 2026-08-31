"""Four engines. Engine 3 never imports tools.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass
from corvus_node.runtime.wire import Wire
from corvus_node.tools.echo import run as echo_run


class Engine1:
    def __init__(self, wire: Wire) -> None:
        self._wire = wire

    async def run_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        call_id: str,
        origin: UUID,
    ) -> dict[str, Any]:
        req = Envelope(
            origin_correlation_id=origin,
            source_engine=EngineId.ENGINE1,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="tool_call",
            payload={"name": name, "arguments": arguments, "id": call_id},
        )
        resp = await self._wire.request(req, claimed_engine=EngineId.ENGINE1)
        if resp.type != "tool_call_response" or not resp.payload.get("approved"):
            result = {"error": resp.payload.get("reason", "denied")}
        elif isinstance(resp.payload.get("result"), dict):
            result = resp.payload["result"]
        elif name == "echo":
            result = echo_run(arguments)
        else:
            result = {"error": f"unknown local tool {name}"}
        done = Envelope(
            origin_correlation_id=origin,
            source_engine=EngineId.ENGINE1,
            destination=Destination.NODE,
            message_class=MessageClass.EVENT,
            type="tool_result",
            payload={"id": call_id, "name": name, "result": result},
        )
        await self._wire.request(done, claimed_engine=EngineId.ENGINE1)
        return result


class Engine2:
    def __init__(self, wire: Wire) -> None:
        self._wire = wire

    async def respond(self, text: str, *, origin: UUID) -> None:
        msg = Envelope(
            origin_correlation_id=origin,
            source_engine=EngineId.ENGINE2,
            destination=Destination.NODE,
            message_class=MessageClass.EVENT,
            type="agent_response",
            payload={"text": text},
        )
        await self._wire.request(msg, claimed_engine=EngineId.ENGINE2)


class Engine3:
    """Inference client only. Must not import or call tools."""

    def __init__(self, wire: Wire) -> None:
        self._wire = wire

    async def infer(
        self,
        messages: list[dict[str, Any]],
        *,
        origin: UUID,
        tools_schema: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"messages": messages}
        if tools_schema:
            payload["tools_schema"] = tools_schema
        req = Envelope(
            origin_correlation_id=origin,
            source_engine=EngineId.ENGINE3,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="llm_request",
            payload=payload,
        )
        resp = await self._wire.request(req, claimed_engine=EngineId.ENGINE3)
        if resp.type != "llm_response":
            raise RuntimeError(f"expected llm_response, got {resp.type}")
        return resp.payload


class Engine4:
    def __init__(self, wire: Wire) -> None:
        self._wire = wire

    async def write(self, key: str, value: str, *, origin: UUID) -> None:
        req = Envelope(
            origin_correlation_id=origin,
            source_engine=EngineId.ENGINE4,
            destination=Destination.NODE,
            message_class=MessageClass.REQUEST,
            type="memory:write",
            payload={"key": key, "value": value},
        )
        await self._wire.request(req, claimed_engine=EngineId.ENGINE4)
