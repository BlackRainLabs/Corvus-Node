"""One-turn tests (test socket only — not corvus-node run).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

from corvus_node.identity.principal import Principal, Role, Zone

from .harness import run_paired_chat, run_paired_turn


async def test_plain_turn() -> None:
    text, session = await run_paired_turn("hello")
    assert "hello" in text
    assert "Stub LLM response" in text
    types = session.audit.types()
    assert "handshake" in types
    assert "user_query" in types
    assert "llm_request" in types
    assert "llm_response" in types
    assert "agent_response" in types


async def test_echo_after_rbac() -> None:
    text, session = await run_paired_turn("hello", tools=frozenset({"echo"}))
    assert "Stub LLM after tools" in text
    assert "Hello from echo" in text
    types = session.audit.types()
    assert "tool_call" in types
    assert "tool_result" in types
    decisions = [e.decision for e in session.audit.events() if e.decision]
    assert "allow" in decisions


async def test_tools_come_from_handshake_ok() -> None:
    text, session = await run_paired_turn(
        "hello",
        tools=frozenset({"echo"}),
        guest_tools=frozenset(),
    )
    assert "Stub LLM after tools" in text
    assert "Hello from echo" in text
    types = session.audit.types()
    assert "handshake_ok" in types
    assert "tool_call" in types


async def test_file_read_after_rbac(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("from disk", encoding="utf-8")
    text, session = await run_paired_turn(
        "hello",
        tools=frozenset({"file_read"}),
        workspace_paths=(str(tmp_path),),
    )
    assert "from disk" in text
    assert "Stub LLM after tools" in text
    types = session.audit.types()
    assert "tool_call" in types
    assert "tool_result" in types


async def test_file_write_after_edit_prompt(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("old", encoding="utf-8")
    text, session = await run_paired_turn(
        "edit notes.txt to 'reviewed'",
        tools=frozenset({"file_write"}),
        workspace_paths=(str(tmp_path),),
    )
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "reviewed"
    assert "Stub LLM after tools" in text
    assert "tool_call" in session.audit.types()


async def test_review_sees_live_user_edit(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("first draft", encoding="utf-8")
    text, _ = await run_paired_turn(
        "review notes.txt",
        tools=frozenset({"file_read"}),
        workspace_paths=(str(tmp_path),),
    )
    assert "first draft" in text
    notes.write_text("user edited", encoding="utf-8")
    text, _ = await run_paired_turn(
        "review notes.txt",
        tools=frozenset({"file_read"}),
        workspace_paths=(str(tmp_path),),
    )
    assert "user edited" in text
    assert "first draft" not in text


async def test_channel_user_does_not_inherit_echo() -> None:
    text, session = await run_paired_turn(
        "hello",
        tools=frozenset({"echo"}),
        principal=Principal(issuer="telegram", subject="1", role=Role.USER, zone=Zone.CHANNEL),
    )
    assert "Stub LLM response" in text
    types = session.audit.types()
    assert "tool_call" not in types


async def test_two_turns_same_session() -> None:
    texts, session = await run_paired_chat(["hello", "hello again"])
    assert len(texts) == 2
    assert "hello" in texts[0]
    assert "hello again" in texts[1]
    assert session.audit.types().count("user_query") == 2
    assert "session_end" in session.audit.types()


async def test_chat_write_then_review_same_session(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("old", encoding="utf-8")
    texts, _ = await run_paired_chat(
        ["edit notes.txt to 'reviewed'", "review notes.txt"],
        tools=frozenset({"file_read", "file_write"}),
        workspace_paths=(str(tmp_path),),
    )
    assert notes.read_text(encoding="utf-8") == "reviewed"
    assert "reviewed" in texts[1]
