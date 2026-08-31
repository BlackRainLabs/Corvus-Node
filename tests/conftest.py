"""Shared pytest fixtures.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

import pytest

from corvus_node.node.control import (
    control_socket_path,
    pid_file_path,
    read_frame,
    write_frame,
)


@pytest.fixture(autouse=True)
def isolate_host_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("CORVUS_NODE_SKIP_UPDATE_CHECK", "1")


class FakeNode:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError(f"fake Node failed: {self._error}")

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except Exception as exc:
            self._error = exc
        finally:
            self.loop.close()

    async def _serve(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.unlink(missing_ok=True)
        halt = asyncio.Event()

        async def on_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                while True:
                    msg = await read_frame(reader)
                    if msg is None:
                        return
                    if msg["type"] == "status":
                        await write_frame(
                            writer,
                            "status_ok",
                            {
                                "state": "running",
                                "pid": 1,
                                "vm_instance_id": "vmtest",
                                "tools": ["echo"],
                                "workspace": [],
                                "llm": "stub",
                            },
                        )
                    elif msg["type"] == "start":
                        await write_frame(
                            writer,
                            "start_ok",
                            {
                                "state": "running",
                                "pid": 1,
                                "vm_instance_id": "vmtest",
                                "tools": msg.get("payload", {}).get("tools") or ["echo"],
                                "workspace": msg.get("payload", {}).get("workspace") or [],
                                "llm": "stub",
                            },
                        )
                    elif msg["type"] == "stop":
                        await write_frame(writer, "stop_ok", {"state": "idle"})
                        return
                    elif msg["type"] == "shutdown":
                        pid_file_path().unlink(missing_ok=True)
                        await write_frame(writer, "shutdown_ok", {})
                        self.path.unlink(missing_ok=True)
                        halt.set()
                        return
                    elif msg["type"] == "chat_attach":
                        await write_frame(writer, "waiting", {})
                        while True:
                            inner = await read_frame(reader)
                            if inner is None:
                                return
                            if inner["type"] == "user":
                                text = str(inner["payload"].get("text", ""))
                                await write_frame(writer, "agent", {"text": f"reply:{text}"})
                                await write_frame(writer, "waiting", {})
                            elif inner["type"] == "stop":
                                await write_frame(writer, "stop_ok", {"state": "idle"})
                                return
                    else:
                        await write_frame(
                            writer, "error", {"code": "unknown", "reason": msg["type"]}
                        )
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        server = await asyncio.start_unix_server(on_conn, path=str(self.path))
        pid_path = pid_file_path()
        pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self._ready.set()
        try:
            await halt.wait()
        finally:
            server.close()
            await server.wait_closed()
            pid_file_path().unlink(missing_ok=True)
            self.path.unlink(missing_ok=True)


@pytest.fixture
def fake_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeNode:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    node = FakeNode(control_socket_path())
    node.start()
    return node
