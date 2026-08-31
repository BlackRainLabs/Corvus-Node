"""Deterministic stub LLM (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from corvus_node.llm.stub import StubLlm

_READ = [{"name": "file_read"}]
_WRITE = [{"name": "file_write"}]
_BOTH = [{"name": "file_read"}, {"name": "file_write"}]
_ECHO = [{"name": "echo"}]


def test_chat_without_tools() -> None:
    out = StubLlm().complete([{"role": "user", "content": "hello"}])
    assert out.tool_calls == []
    assert "hello" in out.content


def test_hello_with_echo() -> None:
    out = StubLlm().complete([{"role": "user", "content": "hello"}], tools_schema=_ECHO)
    assert out.tool_calls[0]["name"] == "echo"


def test_hello_with_file_read_defaults_hello_txt() -> None:
    out = StubLlm().complete([{"role": "user", "content": "hello"}], tools_schema=_READ)
    assert out.tool_calls[0]["name"] == "file_read"
    assert out.tool_calls[0]["arguments"]["path"] == "hello.txt"


def test_review_named_file() -> None:
    out = StubLlm().complete(
        [{"role": "user", "content": "review notes.txt"}],
        tools_schema=_READ,
    )
    assert out.tool_calls[0]["name"] == "file_read"
    assert out.tool_calls[0]["arguments"]["path"] == "notes.txt"


def test_edit_named_file() -> None:
    out = StubLlm().complete(
        [{"role": "user", "content": "edit notes.txt to 'done'"}],
        tools_schema=_WRITE,
    )
    call = out.tool_calls[0]
    assert call["name"] == "file_write"
    assert call["arguments"]["path"] == "notes.txt"
    assert call["arguments"]["content"] == "done"


def test_edit_prefers_write_when_both_allowed() -> None:
    out = StubLlm().complete(
        [{"role": "user", "content": "edit notes.txt"}],
        tools_schema=_BOTH,
    )
    assert [c["name"] for c in out.tool_calls] == ["file_write"]


def test_review_prefers_read_when_both_allowed() -> None:
    out = StubLlm().complete(
        [{"role": "user", "content": "review notes.txt"}],
        tools_schema=_BOTH,
    )
    assert [c["name"] for c in out.tool_calls] == ["file_read"]


def test_after_tools_ignores_prior_turn_tools() -> None:
    out = StubLlm().complete(
        [
            {"role": "user", "content": "edit notes.txt to 'done'"},
            {"role": "tool", "content": "{'ok': True}"},
            {"role": "assistant", "content": "Stub LLM after tools"},
            {"role": "user", "content": "review notes.txt"},
        ],
        tools_schema=_BOTH,
    )
    assert out.tool_calls[0]["name"] == "file_read"
    assert out.tool_calls[0]["arguments"]["path"] == "notes.txt"


def test_after_tools_stops() -> None:
    out = StubLlm().complete(
        [
            {"role": "user", "content": "review notes.txt"},
            {"role": "tool", "content": "{'content': 'hi'}"},
        ],
        tools_schema=_READ,
    )
    assert out.tool_calls == []
    assert "after tools" in out.content
