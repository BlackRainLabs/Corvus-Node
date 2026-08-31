"""Deterministic stub LLM for CI. Not a provider.

New tools and LLM-facing features must land here first so `make test` can
exercise the path. See AGENTS.md (stub first) and tests/test_stub.py.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_PATH = re.compile(r"([\w./-]+\.\w+)")
_WRITE = ("edit", "write", "fix", "change", "update", "create", "replace")
_READ = ("read", "review", "open", "show", "cat", "look")


@dataclass(frozen=True)
class StubCompletion:
    content: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str


def _tools_after_last_user(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trailing: list[dict[str, Any]] = []
    for message in reversed(messages):
        role = str(message.get("role"))
        if role == "user":
            break
        if role == "tool":
            trailing.append(message)
    trailing.reverse()
    return trailing


def _last_user(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role")) == "user":
            return str(message.get("content", ""))
    return ""


def _schema_names(tools_schema: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in tools_schema:
        name = str(entry.get("name") or (entry.get("function") or {}).get("name") or "")
        if name:
            names.append(name)
    return names


def _path(text: str) -> str:
    match = _PATH.search(text)
    return match.group(1) if match else "hello.txt"


def _write_content(text: str) -> str:
    quoted = re.search(r"""to\s+["'](.+)["']""", text)
    if quoted:
        return quoted.group(1)
    say = re.search(r"\bsay\s+(.+)$", text, re.IGNORECASE)
    if say:
        return say.group(1).strip()
    return "hello from file_write"


def _pick_calls(text: str, names: list[str]) -> list[tuple[str, dict[str, str]]]:
    """Pick one tool from the allowlist using the user text. Not a model."""
    available = set(names)
    lower = text.lower()
    path = _path(text)
    write = any(word in lower for word in _WRITE)
    read = any(word in lower for word in _READ)
    if write and "file_write" in available:
        return [("file_write", {"path": path, "content": _write_content(text)})]
    if "file_read" in available and (read or "echo" not in available):
        return [("file_read", {"path": path})]
    if "echo" in available:
        return [("echo", {"text": "Hello from echo"})]
    if "file_write" in available:
        return [("file_write", {"path": path, "content": _write_content(text)})]
    return []


class StubLlm:
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]] | None = None,
    ) -> StubCompletion:
        tool_messages = _tools_after_last_user(messages)
        if tool_messages:
            combined = "; ".join(str(m.get("content", "")) for m in tool_messages)
            return StubCompletion(
                content=f"Stub LLM after tools: {combined}",
                tool_calls=[],
                finish_reason="stop",
            )
        last_user = _last_user(messages)
        if tools_schema:
            calls = []
            picked = _pick_calls(last_user, _schema_names(tools_schema))
            for index, (name, args) in enumerate(picked):
                calls.append(
                    {
                        "id": f"call_stub_{index + 1}",
                        "name": name,
                        "arguments": args,
                    }
                )
            if calls:
                return StubCompletion(content="", tool_calls=calls, finish_reason="tool_calls")
        text = f"Stub LLM response: {last_user}" if last_user else "Stub LLM response for turn."
        return StubCompletion(content=text, tool_calls=[], finish_reason="stop")


def dump_tool_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments)
