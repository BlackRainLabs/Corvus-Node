"""Host Node session: firewall RBAC, hop MAC, LLM gateway, inbound user_query.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from corvus_node.audit.store import AuditStore
from corvus_node.identity.principal import Principal, operator_principal
from corvus_node.llm.stub import StubLlm
from corvus_node.memory.service import MemoryService
from corvus_node.node.workspace import (
    WorkspaceError,
    host_file_read,
    host_file_write,
    resolve_host_workspace,
)
from corvus_node.policy.engine import FILE_TOOLS, PolicyEngine
from corvus_node.protocol.codec import CodecError, decode_line, encode_message
from corvus_node.protocol.mac import HopMac, MacError, new_session_key
from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass

DENY_BURST = 3
MAX_MESSAGES = 64
MAX_BYTES = 1_048_576
MAX_SESSION_TURNS = 32
TURN_TIMEOUT_SEC = 90.0
TOOL_RESULT_MAX = 65_536


@dataclass
class LaunchConfig:
    agent_id: str = "agent-0"
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    workspace_paths: tuple[str, ...] = ()
    user_text: str = ""
    once: bool = True
    prompts: asyncio.Queue[str | None] | None = None
    responses: asyncio.Queue[str | None] | None = None
    on_waiting_prompt: Callable[[], None] | None = None
    principal: Principal = field(default_factory=operator_principal)
    vm_instance_id: str = field(default_factory=lambda: uuid4().hex)
    guest_cid: int = 3


class NodeSession:
    def __init__(
        self,
        config: LaunchConfig,
        *,
        policy: PolicyEngine | None = None,
        audit: AuditStore | None = None,
        llm: StubLlm | None = None,
        memory: MemoryService | None = None,
        session_key: str | None = None,
    ) -> None:
        self.config = config
        self.policy = policy or PolicyEngine(
            agent_id=config.agent_id,
            allowed_tools=config.allowed_tools,
            workspace_paths=config.workspace_paths,
            principal=config.principal,
        )
        self.audit = audit or AuditStore()
        self.llm = llm or StubLlm()
        self.memory = memory or MemoryService()
        self.final_response: str | None = None
        self._origin: UUID | None = None
        self._session_key = session_key or new_session_key()
        self.mac = HopMac(
            self._session_key,
            vm_instance_id=config.vm_instance_id,
            guest_cid=config.guest_cid,
        )
        self._deny_streak = 0
        self._outstanding_calls: set[str] = set()
        self._messages = 0
        self._bytes = 0
        self._turns = 0
        self._awaiting_guest = True
        self._turn_deadline: float | None = None

    def _sign(self, envelope: Envelope) -> Envelope:
        return self.mac.sign(envelope)

    def _reply(
        self,
        incoming: Envelope,
        *,
        type_: str,
        payload: dict[str, Any],
        dest_target: str = "",
    ) -> Envelope:
        dest = EngineId(incoming.source_engine)
        return self._sign(
            Envelope(
                correlation_id=incoming.correlation_id,
                origin_correlation_id=incoming.origin_correlation_id or incoming.correlation_id,
                source_engine=EngineId.NODE,
                destination=Destination.ENGINE,
                dest_target=dest_target or dest.value,
                message_class=MessageClass.RESPONSE,
                type=type_,
                payload=payload,
            )
        )

    def _note_decision(self, decision: str) -> None:
        if decision == "deny":
            self._deny_streak += 1
            if self._deny_streak >= DENY_BURST:
                self.audit.log_flag(
                    code="deny_burst",
                    message_type="policy",
                    source_engine=str(EngineId.NODE),
                    correlation_id=self._origin or uuid4(),
                    origin_correlation_id=self._origin,
                    details={"streak": self._deny_streak},
                )
        else:
            self._deny_streak = 0

    def _workspace_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.config.workspace_paths:
            return {"error": "no workspace"}
        try:
            root = resolve_host_workspace(self.config.workspace_paths[0])
        except WorkspaceError as exc:
            return {"error": str(exc)}
        path = str(arguments.get("path", ""))
        if name == "file_read":
            return host_file_read(root, path)
        return host_file_write(root, path, str(arguments.get("content", "")))

    async def _send_session_init(self, writer: asyncio.StreamWriter) -> None:
        init = self._sign(
            Envelope(
                source_engine=EngineId.NODE,
                destination=Destination.LOOP,
                dest_target="loop",
                message_class=MessageClass.SYSTEM,
                type="session_init",
                payload={
                    "session_key": self._session_key,
                    "vm_instance_id": self.config.vm_instance_id,
                    "guest_cid": self.config.guest_cid,
                },
            )
        )
        self.audit.log_hop(
            message_type="session_init",
            source_engine=str(EngineId.NODE),
            correlation_id=init.correlation_id,
            origin_correlation_id=init.origin_correlation_id,
        )
        writer.write((encode_message(init) + "\n").encode("utf-8"))
        await writer.drain()

    def _user_query_envelope(self, text: str) -> Envelope:
        self._origin = uuid4()
        return self._sign(
            Envelope(
                correlation_id=self._origin,
                origin_correlation_id=self._origin,
                source_engine=EngineId.NODE,
                destination=Destination.LOOP,
                dest_target="loop",
                message_class=MessageClass.REQUEST,
                type="user_query",
                payload={"text": text},
            )
        )

    def _session_end_envelope(self) -> Envelope:
        return self._sign(
            Envelope(
                source_engine=EngineId.NODE,
                destination=Destination.LOOP,
                dest_target="loop",
                message_class=MessageClass.SYSTEM,
                type="session_end",
                payload={},
            )
        )

    async def _write(self, writer: asyncio.StreamWriter, envelope: Envelope) -> None:
        self.audit.log_hop(
            message_type=envelope.type,
            source_engine=str(envelope.source_engine),
            correlation_id=envelope.correlation_id,
            origin_correlation_id=envelope.origin_correlation_id,
        )
        writer.write((encode_message(envelope) + "\n").encode("utf-8"))
        await writer.drain()

    def _arm_guest_wait(self) -> None:
        self._awaiting_guest = True
        self._messages = 0
        self._bytes = 0
        self._turn_deadline = asyncio.get_running_loop().time() + TURN_TIMEOUT_SEC

    async def _send_user_query(self, writer: asyncio.StreamWriter, text: str) -> None:
        self._turns += 1
        self._arm_guest_wait()
        await self._write(writer, self._user_query_envelope(text))

    async def _send_session_end(self, writer: asyncio.StreamWriter) -> None:
        self._awaiting_guest = False
        self._turn_deadline = None
        await self._write(writer, self._session_end_envelope())

    async def _next_prompt(self) -> str | None:
        if self.config.once:
            return self.config.user_text
        if self.config.on_waiting_prompt is not None:
            self.config.on_waiting_prompt()
        if self.config.prompts is None:
            return None
        return await self.config.prompts.get()

    async def _after_agent_response(self, writer: asyncio.StreamWriter) -> bool:
        """Return True when the session should stop."""
        self._awaiting_guest = False
        self._turn_deadline = None
        if self.config.responses is not None and self.final_response is not None:
            await self.config.responses.put(self.final_response)
        if self.config.once or self._turns >= MAX_SESSION_TURNS:
            await self._send_session_end(writer)
            return True
        nxt = await self._next_prompt()
        if nxt is None:
            await self._send_session_end(writer)
            return True
        await self._send_user_query(writer, nxt)
        return False

    async def serve(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> str:
        """Handle a guest connection until session_end. Returns last agent text."""
        await self._send_session_init(writer)
        handshake_done = False
        self._arm_guest_wait()
        while True:
            timeout: float | None = None
            if self._awaiting_guest and self._turn_deadline is not None:
                timeout = max(0.05, self._turn_deadline - asyncio.get_running_loop().time())
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            except TimeoutError:
                self.audit.log_flag(
                    code="turn_cap",
                    message_type="cap",
                    source_engine=str(EngineId.NODE),
                    correlation_id=self._origin or uuid4(),
                    origin_correlation_id=self._origin,
                    details={"reason": "turn timeout"},
                )
                await self._send_session_end(writer)
                break
            if not line:
                break
            self._messages += 1
            self._bytes += len(line)
            if self._messages > MAX_MESSAGES or self._bytes > MAX_BYTES:
                self.audit.log_flag(
                    code="turn_cap",
                    message_type="cap",
                    source_engine=str(EngineId.NODE),
                    correlation_id=self._origin or uuid4(),
                    origin_correlation_id=self._origin,
                    details={"messages": self._messages, "bytes": self._bytes},
                )
                await self._send_session_end(writer)
                break
            try:
                msg = decode_line(line.decode("utf-8"))
                self.mac.verify(msg)
            except (MacError, CodecError) as exc:
                code = exc.code if isinstance(exc, MacError) else "mac_fail"
                self.audit.log_flag(
                    code=code,
                    message_type="mac",
                    source_engine=str(EngineId.NODE),
                    correlation_id=self._origin or uuid4(),
                    origin_correlation_id=self._origin,
                    details={"reason": str(exc)},
                )
                break
            self.audit.log_hop(
                message_type=msg.type,
                source_engine=str(msg.source_engine),
                correlation_id=msg.correlation_id,
                origin_correlation_id=msg.origin_correlation_id,
            )
            if not handshake_done and msg.type != "handshake":
                self.audit.log_flag(
                    code="pre_handshake",
                    message_type=msg.type,
                    source_engine=str(msg.source_engine),
                    correlation_id=msg.correlation_id,
                    origin_correlation_id=msg.origin_correlation_id,
                )
                break
            reply: Envelope | None = None
            if msg.type == "handshake":
                handshake_done = True
                visible = sorted(self.policy.visible_tools())
                reply = self._reply(
                    msg,
                    type_="handshake_ok",
                    payload={
                        "agent_id": self.config.agent_id,
                        "allowed_tools": visible,
                    },
                )
            elif msg.type == "llm_request":
                decision = self.policy.evaluate(msg)
                self.audit.log_hop(
                    message_type="policy",
                    source_engine=str(msg.source_engine),
                    correlation_id=msg.correlation_id,
                    origin_correlation_id=msg.origin_correlation_id,
                    decision=decision.decision,
                    details={"rule_id": decision.rule_id, "reason": decision.reason},
                )
                self._note_decision(decision.decision)
                if decision.decision != "allow":
                    reply = self._reply(
                        msg,
                        type_="error",
                        payload={"code": "RBAC_DENIED", "reason": decision.reason},
                    )
                else:
                    schema = msg.payload.get("tools_schema")
                    visible = self.policy.visible_tools()
                    if schema:
                        schema = [
                            entry for entry in schema if str(entry.get("name", "")) in visible
                        ]
                    completion = self.llm.complete(
                        list(msg.payload.get("messages") or []),
                        tools_schema=schema,
                    )
                    calls = [
                        call
                        for call in completion.tool_calls
                        if str(call.get("name", "")) in visible
                    ]
                    reply = self._reply(
                        msg,
                        type_="llm_response",
                        payload={
                            "content": completion.content,
                            "tool_calls": calls,
                            "finish_reason": "tool_calls" if calls else "stop",
                        },
                    )
            elif msg.type == "tool_call":
                decision = self.policy.evaluate(msg)
                self.audit.log_hop(
                    message_type="policy",
                    source_engine=str(msg.source_engine),
                    correlation_id=msg.correlation_id,
                    origin_correlation_id=msg.origin_correlation_id,
                    decision=decision.decision,
                    details={"rule_id": decision.rule_id, "tool": msg.payload.get("name")},
                )
                if decision.flag_code:
                    self.audit.log_flag(
                        code=decision.flag_code,
                        message_type="tool_call",
                        source_engine=str(msg.source_engine),
                        correlation_id=msg.correlation_id,
                        origin_correlation_id=msg.origin_correlation_id,
                    )
                self._note_decision("deny" if decision.decision != "allow" else "allow")
                if decision.decision == "elevate":
                    self.audit.log_elevate(
                        message_type="tool_call",
                        source_engine=str(msg.source_engine),
                        correlation_id=msg.correlation_id,
                        origin_correlation_id=msg.origin_correlation_id,
                        details={
                            "tool": msg.payload.get("name"),
                            "code": "ELEVATE_REQUIRED",
                        },
                    )
                    reply = self._reply(
                        msg,
                        type_="tool_call_response",
                        payload={
                            "approved": False,
                            "reason": decision.reason,
                            "code": "ELEVATE_REQUIRED",
                        },
                    )
                elif decision.decision == "allow":
                    call_id = str(msg.payload.get("id", ""))
                    if call_id:
                        self._outstanding_calls.add(call_id)
                    payload: dict[str, Any] = {
                        "approved": True,
                        "reason": decision.reason,
                    }
                    name = str(msg.payload.get("name", ""))
                    if name in FILE_TOOLS:
                        arguments = msg.payload.get("arguments")
                        if not isinstance(arguments, dict):
                            arguments = {}
                        payload["result"] = self._workspace_tool(name, arguments)
                    reply = self._reply(
                        msg,
                        type_="tool_call_response",
                        payload=payload,
                    )
                else:
                    reply = self._reply(
                        msg,
                        type_="tool_call_response",
                        payload={
                            "approved": False,
                            "reason": decision.reason,
                        },
                    )
            elif msg.type == "tool_result":
                call_id = str(msg.payload.get("id", ""))
                blob = str(msg.payload.get("result", ""))
                if call_id not in self._outstanding_calls:
                    self.audit.log_flag(
                        code="unbound_tool_result",
                        message_type="tool_result",
                        source_engine=str(msg.source_engine),
                        correlation_id=msg.correlation_id,
                        origin_correlation_id=msg.origin_correlation_id,
                    )
                    reply = self._reply(
                        msg,
                        type_="error",
                        payload={"code": "UNBOUND_TOOL_RESULT", "reason": "no approved call"},
                    )
                elif len(blob) > TOOL_RESULT_MAX:
                    self.audit.log_flag(
                        code="tool_result_too_large",
                        message_type="tool_result",
                        source_engine=str(msg.source_engine),
                        correlation_id=msg.correlation_id,
                        origin_correlation_id=msg.origin_correlation_id,
                    )
                    reply = self._reply(
                        msg,
                        type_="error",
                        payload={"code": "TOOL_RESULT_TOO_LARGE", "reason": "result exceeds cap"},
                    )
                else:
                    self._outstanding_calls.discard(call_id)
                    reply = self._reply(msg, type_="tool_result_ack", payload={"ok": True})
            elif msg.type == "agent_response":
                self.final_response = str(msg.payload.get("text", ""))
                reply = self._reply(msg, type_="agent_response_ack", payload={"ok": True})
            elif msg.type.startswith("memory:"):
                decision = self.policy.evaluate(msg)
                self._note_decision(decision.decision)
                if decision.decision != "allow":
                    reply = self._reply(
                        msg,
                        type_="error",
                        payload={"code": "RBAC_DENIED", "reason": decision.reason},
                    )
                elif msg.type == "memory:write":
                    self.memory.write(
                        str(msg.payload.get("key", "")),
                        str(msg.payload.get("value", "")),
                    )
                    reply = self._reply(msg, type_="memory:write_ok", payload={"ok": True})
                else:
                    value = self.memory.query(str(msg.payload.get("key", "")))
                    reply = self._reply(msg, type_="memory:query_ok", payload={"value": value})
            else:
                reply = self._reply(
                    msg,
                    type_="error",
                    payload={"code": "UNKNOWN_TYPE", "reason": msg.type},
                )

            if reply is not None:
                await self._write(writer, reply)

            if msg.type == "handshake":
                prompt = await self._next_prompt()
                if prompt is None and not self.config.once:
                    await self._send_session_end(writer)
                    break
                await self._send_user_query(writer, prompt or "")
            elif msg.type == "agent_response":
                stop = await self._after_agent_response(writer)
                if stop:
                    break

        return self.final_response or ""
