"""Live operator chat view (CLI). Control frames stay an implementation detail.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import shutil
import signal
import sys
from dataclasses import dataclass
from typing import TextIO

from corvus_node import __version__
from corvus_node.node.control import ControlClient, ControlError
from corvus_node.node.info import LLM_NAME

HEADER_ROWS = 3
EXIT_COMMANDS = frozenset({"/exit", "/quit"})
HELP_COMMANDS = frozenset({"/help"})
_ALT_ENTER = "\033[?1049h"
_ALT_LEAVE = "\033[?1049l"
_CLEAR = "\033[2J"
_HOME = "\033[H"
_RESET_SCROLL = "\033[r"
_REVERSE = "\033[7m"
_RESET = "\033[0m"


@dataclass
class ChatChrome:
    version: str = __version__
    model: str = LLM_NAME
    context: str = ""
    tools: str = ""
    workspace: str = ""


def chrome_from_snapshot(snap: dict) -> ChatChrome:
    tools = snap.get("tools") or []
    workspace = snap.get("workspace") or []
    model = str(snap.get("llm") or LLM_NAME)
    return ChatChrome(
        version=__version__,
        model=model,
        context="",
        tools=",".join(str(t) for t in tools),
        workspace=str(workspace[0]) if workspace else "",
    )


def is_exit_command(text: str) -> bool:
    return text.strip().lower() in EXIT_COMMANDS


def is_help_command(text: str) -> bool:
    return text.strip().lower() in HELP_COMMANDS


def _fit(text: str, width: int) -> str:
    width = max(1, width)
    if len(text) > width:
        if width <= 3:
            return text[:width]
        return text[: width - 3] + "..."
    return text.ljust(width)


def format_header_lines(chrome: ChatChrome, width: int) -> list[str]:
    context = chrome.context.strip() or "—"
    line1 = (
        f" Corvus-Node {chrome.version}  ·  model: {chrome.model}"
        f"  ·  context: {context}  ·  /exit to leave"
    )
    bits: list[str] = []
    if chrome.tools:
        bits.append(f"tools: {chrome.tools}")
    if chrome.workspace:
        bits.append(f"workspace: {chrome.workspace}")
    bits.append("guest stays up until vm stop")
    line2 = " " + "  ·  ".join(bits)
    line3 = "─" * max(1, width)
    return [_fit(line1, width), _fit(line2, width), _fit(line3, width)]


def format_header_plain(chrome: ChatChrome, width: int = 80) -> str:
    return "\n".join(format_header_lines(chrome, width)) + "\n"


def _term_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return max(20, size.columns), max(HEADER_ROWS + 3, size.lines)


def _write_header(stream: TextIO, chrome: ChatChrome, width: int) -> None:
    lines = format_header_lines(chrome, width)
    stream.write(_HOME)
    stream.write(f"{_REVERSE}{lines[0]}{_RESET}\n")
    stream.write(f"{_REVERSE}{lines[1]}{_RESET}\n")
    stream.write(f"{lines[2]}\n")


def _set_scroll(stream: TextIO, rows: int) -> None:
    top = HEADER_ROWS + 1
    stream.write(f"\033[{top};{rows}r")
    stream.write(f"\033[{top};1H")


class _LiveScreen:
    def __init__(self, stream: TextIO, chrome: ChatChrome) -> None:
        self.stream = stream
        self.chrome = chrome
        self._active = False
        self._resized = False

    def _on_winch(self, _signum: int, _frame: object) -> None:
        self._resized = True

    def enter(self) -> None:
        self.stream.write(f"{_ALT_ENTER}{_CLEAR}")
        cols, rows = _term_size()
        _write_header(self.stream, self.chrome, cols)
        _set_scroll(self.stream, rows)
        self.stream.flush()
        self._active = True
        signal.signal(signal.SIGWINCH, self._on_winch)

    def leave(self) -> None:
        if not self._active:
            return
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        self.stream.write(f"{_RESET_SCROLL}{_ALT_LEAVE}")
        self.stream.flush()
        self._active = False

    def maybe_relayout(self) -> None:
        if not self._resized or not self._active:
            return
        self._resized = False
        cols, rows = _term_size()
        self.stream.write("\033[s")
        self.stream.write(_RESET_SCROLL)
        _write_header(self.stream, self.chrome, cols)
        _set_scroll(self.stream, rows)
        self.stream.write("\033[u")
        self.stream.flush()


def _print_reply(stream: TextIO, model: str, text: str) -> None:
    body = text if text.endswith("\n") else f"{text}\n"
    first = True
    for line in body.splitlines(keepends=True):
        if first:
            stream.write(f"{model}  {line}")
            first = False
        else:
            pad = " " * (len(model) + 2)
            stream.write(f"{pad}{line}")
    stream.flush()


def run_live_chat(
    client: ControlClient,
    chrome: ChatChrome,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Attach loop: conversation until /exit. Does not stop the guest VM."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr
    tty = bool(stdin.isatty() and stdout.isatty())
    screen: _LiveScreen | None = None
    prompt = "you  "
    if tty:
        screen = _LiveScreen(stdout, chrome)
        screen.enter()
    else:
        stderr.write(format_header_plain(chrome))
        stderr.flush()
    try:
        while True:
            if screen is not None:
                screen.maybe_relayout()
            stderr.write(prompt)
            stderr.flush()
            try:
                line = stdin.readline()
            except InterruptedError:
                continue
            if line == "":
                stderr.write("corvus: stdin closed\n")
                stderr.flush()
                return 0
            text = line.strip()
            if not text:
                continue
            if is_exit_command(text):
                return 0
            if is_help_command(text):
                stderr.write("Live chat. /exit leaves (VM stays up). /help this text.\n")
                stderr.flush()
                continue
            client.send("user", {"text": text})
            while True:
                reply = client.read()
                if reply["type"] == "agent":
                    _print_reply(stdout, chrome.model, str(reply["payload"].get("text", "")))
                    continue
                if reply["type"] == "waiting":
                    break
                stderr.write(f"corvus: unexpected chat reply {reply['type']}\n")
                stderr.flush()
                return 2
    except ControlError as exc:
        stderr.write(f"corvus: {exc}\n")
        stderr.flush()
        return 2
    finally:
        if screen is not None:
            screen.leave()
    return 0
