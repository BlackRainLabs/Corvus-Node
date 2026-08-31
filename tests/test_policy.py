"""RBAC tests.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from corvus_node.identity.principal import Principal, Role, Zone, operator_principal
from corvus_node.policy.engine import PolicyEngine
from corvus_node.protocol.models import Destination, EngineId, Envelope, MessageClass


def _msg(engine: EngineId, type_: str, payload: dict | None = None) -> Envelope:
    return Envelope(
        source_engine=engine,
        destination=Destination.NODE,
        message_class=MessageClass.REQUEST,
        type=type_,
        payload=payload or {},
    )


def test_engine3_llm_allowed() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"echo"}))
    assert policy.evaluate(_msg(EngineId.ENGINE3, "llm_request")).decision == "allow"


def test_engine3_tool_denied() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"echo"}))
    decision = policy.evaluate(_msg(EngineId.ENGINE3, "tool_call", {"name": "echo"}))
    assert decision.decision == "deny"


def test_unknown_tool_denied() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"echo"}))
    decision = policy.evaluate(_msg(EngineId.ENGINE1, "tool_call", {"name": "rm"}))
    assert decision.decision == "deny"
    assert decision.flag_code == "unknown_tool"


def test_echo_allowed_for_operator() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"echo"}))
    decision = policy.evaluate(_msg(EngineId.ENGINE1, "tool_call", {"name": "echo"}))
    assert decision.decision == "allow"


def test_echo_denied_for_channel_user() -> None:
    user = Principal(issuer="telegram", subject="1", role=Role.USER, zone=Zone.CHANNEL)
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"echo"}), principal=user)
    decision = policy.evaluate(_msg(EngineId.ENGINE1, "tool_call", {"name": "echo"}))
    assert decision.decision == "deny"
    assert policy.visible_tools() == frozenset()


def test_chat_default_deny_memory() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset())
    decision = policy.evaluate(_msg(EngineId.ENGINE4, "memory:write", {"key": "k", "value": "v"}))
    assert decision.decision == "deny"


def test_operator_visible_echo() -> None:
    policy = PolicyEngine(
        agent_id="a",
        allowed_tools=frozenset({"echo"}),
        principal=operator_principal(),
    )
    assert policy.visible_tools() == frozenset({"echo"})


def test_risky_tool_elevates_for_channel_user() -> None:
    user = Principal(issuer="telegram", subject="1", role=Role.USER, zone=Zone.CHANNEL)
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"shell"}), principal=user)
    decision = policy.evaluate(_msg(EngineId.ENGINE1, "tool_call", {"name": "shell"}))
    assert decision.decision == "elevate"


def test_operator_visible_file_read() -> None:
    policy = PolicyEngine(
        agent_id="a",
        allowed_tools=frozenset({"file_read"}),
        workspace_paths=("/tmp/ws",),
    )
    assert policy.visible_tools() == frozenset({"file_read"})


def test_file_tools_hidden_without_workspace() -> None:
    policy = PolicyEngine(agent_id="a", allowed_tools=frozenset({"file_read", "file_write"}))
    assert policy.visible_tools() == frozenset()


def test_file_read_allowed_for_operator() -> None:
    policy = PolicyEngine(
        agent_id="a",
        allowed_tools=frozenset({"file_read"}),
        workspace_paths=("/tmp/ws",),
    )
    decision = policy.evaluate(
        _msg(
            EngineId.ENGINE1,
            "tool_call",
            {"name": "file_read", "arguments": {"path": "hello.txt"}},
        )
    )
    assert decision.decision == "allow"


def test_file_write_elevates_for_channel_user() -> None:
    user = Principal(issuer="telegram", subject="1", role=Role.USER, zone=Zone.CHANNEL)
    policy = PolicyEngine(
        agent_id="a",
        allowed_tools=frozenset({"file_write"}),
        principal=user,
        workspace_paths=("/tmp/ws",),
    )
    decision = policy.evaluate(
        _msg(
            EngineId.ENGINE1,
            "tool_call",
            {"name": "file_write", "arguments": {"path": "hello.txt", "content": "x"}},
        )
    )
    assert decision.decision == "elevate"


def test_path_escape_denied() -> None:
    policy = PolicyEngine(
        agent_id="a",
        allowed_tools=frozenset({"file_read"}),
        workspace_paths=("/tmp/ws",),
    )
    for path in ("../etc/passwd", "/etc/passwd", "/workspace/../etc/passwd", ""):
        decision = policy.evaluate(
            _msg(
                EngineId.ENGINE1,
                "tool_call",
                {"name": "file_read", "arguments": {"path": path}},
            )
        )
        assert decision.decision == "deny"
        assert decision.flag_code == "path_escape"
