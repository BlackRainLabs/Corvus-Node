"""Live chat header and slash commands (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from corvus_node.node.chatview import (
    ChatChrome,
    chrome_from_snapshot,
    format_header_plain,
    is_exit_command,
    is_help_command,
)


def test_header_names_exit_model_and_empty_context() -> None:
    text = format_header_plain(
        ChatChrome(version="0.1.5", model="stub", context="", tools="echo", workspace="/tmp/ws")
    )
    assert "/exit to leave" in text
    assert "model: stub" in text
    assert "context: —" in text
    assert "tools: echo" in text
    assert "workspace: /tmp/ws" in text
    assert "vm stop" in text


def test_chrome_from_snapshot() -> None:
    chrome = chrome_from_snapshot(
        {"llm": "stub", "tools": ["echo"], "workspace": ["/home/null/proj"]}
    )
    assert chrome.model == "stub"
    assert chrome.tools == "echo"
    assert chrome.workspace == "/home/null/proj"
    assert chrome.context == ""


def test_slash_commands() -> None:
    assert is_exit_command("/exit")
    assert is_exit_command("  /QUIT ")
    assert not is_exit_command(".quit")
    assert is_help_command("/help")
    assert not is_help_command("help")
