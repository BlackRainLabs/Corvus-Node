"""Firewall-style RBAC. Default deny. Chat is the implicit allow.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from corvus_node.identity.principal import Principal, Role, operator_principal
from corvus_node.protocol.models import (
    ALLOWED_OUTBOUND,
    Destination,
    EngineId,
    Envelope,
    MessageClass,
)
from corvus_node.tools.paths import workspace_relpath

TOOL_TAGS: dict[str, str] = {
    "echo": "low",
    "file_read": "low",
    "file_write": "write",
}
FILE_TOOLS = frozenset({"file_read", "file_write"})
RISKY_TAGS = frozenset({"write", "exec", "net"})
Decision = Literal["allow", "deny", "elevate", "flag"]


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    rule_id: str
    reason: str
    flag_code: str | None = None


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    action: Decision
    engine: EngineId | None = None
    message_type: str | None = None
    tool: str | None = None
    principal_id: str | None = None
    role: Role | None = None


def tool_tag(name: str) -> str:
    return TOOL_TAGS.get(name, "exec")


def rules_from_launch(
    *,
    allowed_tools: frozenset[str],
    principal: Principal,
) -> tuple[PolicyRule, ...]:
    """Chat path is implicit. --tools adds operator allow rules only."""
    rules: list[PolicyRule] = [
        PolicyRule("handshake", "allow", message_type="handshake"),
        PolicyRule("llm-engine", "allow", engine=EngineId.ENGINE3, message_type="llm_request"),
        PolicyRule("channel-query", "allow", message_type="user_query"),
        PolicyRule("channel-response", "allow", message_type="agent_response"),
        PolicyRule("tool-result", "allow", engine=EngineId.ENGINE1, message_type="tool_result"),
    ]
    for name in sorted(allowed_tools):
        tag = tool_tag(name)
        if principal.is_operator():
            rules.append(
                PolicyRule(
                    f"tool-{name}",
                    "allow",
                    engine=EngineId.ENGINE1,
                    message_type="tool_call",
                    tool=name,
                    principal_id=principal.id,
                )
            )
        elif tag in RISKY_TAGS:
            rules.append(
                PolicyRule(
                    f"elevate-{name}",
                    "elevate",
                    engine=EngineId.ENGINE1,
                    message_type="tool_call",
                    tool=name,
                    principal_id=principal.id,
                )
            )
    return tuple(rules)


class PolicyEngine:
    """Ordered first-match filter. No LLM inspection."""

    def __init__(
        self,
        *,
        agent_id: str,
        allowed_tools: frozenset[str],
        workspace_paths: tuple[str, ...] = (),
        principal: Principal | None = None,
        rules: tuple[PolicyRule, ...] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.allowed_tools = allowed_tools
        self.workspace_paths = workspace_paths
        self.principal = principal or operator_principal()
        self.rules = (
            rules
            if rules is not None
            else rules_from_launch(
                allowed_tools=allowed_tools,
                principal=self.principal,
            )
        )

    def visible_tools(self) -> frozenset[str]:
        visible: set[str] = set()
        for name in self.allowed_tools:
            probe = Envelope(
                source_engine=EngineId.ENGINE1,
                destination=Destination.NODE,
                message_class=MessageClass.REQUEST,
                type="tool_call",
                payload={"name": name},
            )
            if self.evaluate(probe).decision == "allow":
                visible.add(name)
        return frozenset(visible)

    def evaluate(self, message: Envelope) -> PolicyDecision:
        source = EngineId(message.source_engine)
        if message.type == "handshake":
            if source != EngineId.LOOP:
                return PolicyDecision("deny", "path", "only loop may handshake")
        elif source != EngineId.NODE:
            allowed_types = ALLOWED_OUTBOUND.get(source, frozenset())
            if message.type not in allowed_types:
                return PolicyDecision(
                    "deny",
                    "path",
                    f"engine {source} may not send {message.type}",
                    flag_code="engine_spoof" if message.type == "tool_call" else None,
                )
        if message.type == "tool_call":
            name = str(message.payload.get("name", ""))
            if name not in self.allowed_tools:
                return PolicyDecision(
                    "deny",
                    "tool-allowlist",
                    f"tool {name!r} not in launch allowlist",
                    flag_code="unknown_tool",
                )
            if name in FILE_TOOLS:
                if not self.workspace_paths:
                    return PolicyDecision(
                        "deny",
                        "workspace",
                        "file tools require --workspace",
                    )
                arguments = message.payload.get("arguments")
                if arguments is not None:
                    if not isinstance(arguments, dict):
                        arguments = {}
                    path = str(arguments.get("path", ""))
                    if workspace_relpath(path) is None:
                        return PolicyDecision(
                            "deny",
                            "path",
                            f"path {path!r} is outside /workspace",
                            flag_code="path_escape",
                        )
        for rule in self.rules:
            if self._matches(rule, message, source):
                return PolicyDecision(rule.action, rule.rule_id, f"rule {rule.rule_id}")
        return PolicyDecision("deny", "default-deny", f"no rule for {message.type}")

    def _matches(self, rule: PolicyRule, message: Envelope, source: EngineId) -> bool:
        if rule.engine is not None and source != rule.engine:
            return False
        if rule.message_type is not None and message.type != rule.message_type:
            return False
        if rule.tool is not None:
            if message.type != "tool_call":
                return False
            if str(message.payload.get("name", "")) != rule.tool:
                return False
        if rule.principal_id is not None and self.principal.id != rule.principal_id:
            return False
        if rule.role is not None and self.principal.role != rule.role:
            return False
        return True
