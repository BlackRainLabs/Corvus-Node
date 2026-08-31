"""Node serve process: jailer VM + host control socket.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

from corvus_node.gateway.adapter import LocalCliAdapter
from corvus_node.node.control import (
    ControlClient,
    ControlError,
    apply_socket_perms,
    clear_stale_runtime,
    control_socket_path,
    node_log_path,
    node_pid,
    pid_file_path,
    prepare_runtime_dir,
    read_frame,
    write_frame,
)
from corvus_node.node.session import LaunchConfig
from corvus_node.vm.launcher import (
    TURN_TIMEOUT_SEC,
    GuestBootTimeout,
    IsolationUnavailable,
    launch_turn,
)

READY_WAIT_SEC = TURN_TIMEOUT_SEC
START_POLL_SEC = 0.1


class AlreadyRunning(RuntimeError):
    """A guest VM is already up on this Node."""


@dataclass
class ServeState:
    config: LaunchConfig
    prompts: asyncio.Queue[str | None] | None = None
    responses: asyncio.Queue[str | None] | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    shutdown: asyncio.Event = field(default_factory=asyncio.Event)
    chat_attached: bool = False
    boot_task: asyncio.Task[str] | None = None

    def vm_up(self) -> bool:
        return self.boot_task is not None and not self.boot_task.done()

    def snapshot(self) -> dict:
        return {
            "state": "running" if self.vm_up() else "idle",
            "pid": os.getpid(),
            "vm_instance_id": self.config.vm_instance_id if self.vm_up() else "",
            "tools": sorted(self.config.allowed_tools) if self.vm_up() else [],
            "workspace": list(self.config.workspace_paths) if self.vm_up() else [],
            "llm": "stub",
        }

    def request_stop(self) -> None:
        self.stop.set()
        if self.prompts is not None:
            try:
                self.prompts.put_nowait(None)
            except Exception:
                pass
        if self.responses is not None:
            try:
                self.responses.put_nowait(None)
            except Exception:
                pass


def _write_pid() -> None:
    path = pid_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    os.chmod(path, 0o640)


def _unlink_runtime() -> None:
    control_socket_path().unlink(missing_ok=True)
    pid_file_path().unlink(missing_ok=True)


def _config_from_payload(payload: dict) -> LaunchConfig:
    tools = payload.get("tools") or []
    workspace = payload.get("workspace") or []
    adapter = LocalCliAdapter("")
    return LaunchConfig(
        allowed_tools=frozenset(str(t) for t in tools),
        workspace_paths=tuple(str(p) for p in workspace),
        principal=adapter.principal(),
        once=False,
    )


async def _boot_vm(state: ServeState, config: LaunchConfig) -> None:
    prompts: asyncio.Queue[str | None] = asyncio.Queue()
    responses: asyncio.Queue[str | None] = asyncio.Queue()
    config.once = False
    config.prompts = prompts
    config.responses = responses
    state.config = config
    state.prompts = prompts
    state.responses = responses
    state.ready = asyncio.Event()
    state.stop = asyncio.Event()
    config.on_waiting_prompt = lambda: state.ready.set()
    state.boot_task = asyncio.create_task(launch_turn(config))
    ready_task = asyncio.create_task(state.ready.wait())
    try:
        finished, _ = await asyncio.wait(
            {state.boot_task, ready_task},
            timeout=READY_WAIT_SEC,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if state.boot_task in finished:
            await state.boot_task
            raise GuestBootTimeout("guest session ended before handshake")
        if not finished or not state.ready.is_set():
            state.boot_task.cancel()
            raise GuestBootTimeout(f"guest did not handshake within {int(READY_WAIT_SEC)}s")
    finally:
        ready_task.cancel()


async def _stop_vm(state: ServeState) -> None:
    if state.boot_task is None:
        return
    state.request_stop()
    try:
        await state.boot_task
    except (asyncio.CancelledError, Exception):
        pass
    state.boot_task = None
    state.prompts = None
    state.responses = None
    state.chat_attached = False


async def _handle_control(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: ServeState,
) -> None:
    try:
        while True:
            msg = await read_frame(reader)
            if msg is None:
                return
            type_ = msg["type"]
            payload = msg.get("payload") or {}
            if type_ == "status":
                await write_frame(writer, "status_ok", state.snapshot())
            elif type_ == "settings_get":
                await write_frame(
                    writer,
                    "settings_ok",
                    {
                        "tools": sorted(state.config.allowed_tools) if state.vm_up() else [],
                        "workspace": list(state.config.workspace_paths) if state.vm_up() else [],
                    },
                )
            elif type_ == "start":
                if state.vm_up():
                    await write_frame(
                        writer,
                        "error",
                        {"code": "busy", "reason": "guest VM already running"},
                    )
                    continue
                try:
                    await _boot_vm(state, _config_from_payload(payload))
                except (GuestBootTimeout, IsolationUnavailable, OSError) as exc:
                    await write_frame(
                        writer,
                        "error",
                        {"code": "boot", "reason": str(exc)},
                    )
                    await _stop_vm(state)
                    continue
                await write_frame(writer, "start_ok", state.snapshot())
            elif type_ == "stop":
                await _stop_vm(state)
                await write_frame(writer, "stop_ok", {"state": "idle"})
            elif type_ == "shutdown":
                await _stop_vm(state)
                await write_frame(writer, "shutdown_ok", {})
                state.shutdown.set()
                return
            elif type_ == "chat_attach":
                if not state.vm_up():
                    await write_frame(
                        writer,
                        "error",
                        {
                            "code": "idle",
                            "reason": "guest VM is not running; corvus vm start",
                        },
                    )
                    return
                if state.chat_attached:
                    await write_frame(
                        writer,
                        "error",
                        {"code": "busy", "reason": "chat already attached"},
                    )
                    return
                state.chat_attached = True
                try:
                    await write_frame(writer, "waiting", {})
                    while True:
                        inner = await read_frame(reader)
                        if inner is None:
                            return
                        if inner["type"] == "stop":
                            await _stop_vm(state)
                            await write_frame(writer, "stop_ok", {"state": "idle"})
                            return
                        if inner["type"] != "user":
                            await write_frame(
                                writer,
                                "error",
                                {"code": "unknown", "reason": inner["type"]},
                            )
                            continue
                        text = str((inner.get("payload") or {}).get("text", ""))
                        assert state.prompts is not None
                        assert state.responses is not None
                        await state.prompts.put(text)
                        reply = await state.responses.get()
                        if reply is None:
                            await write_frame(
                                writer,
                                "error",
                                {"code": "stopped", "reason": "guest VM stopped"},
                            )
                            return
                        await write_frame(writer, "agent", {"text": reply})
                        await write_frame(writer, "waiting", {})
                finally:
                    state.chat_attached = False
                return
            else:
                await write_frame(
                    writer,
                    "error",
                    {"code": "unknown", "reason": type_},
                )
    except (ControlError, ConnectionResetError, BrokenPipeError, UnicodeDecodeError):
        return
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def serve_forever(config: LaunchConfig) -> None:
    """Bind the control socket (idle), boot a VM on start, stay up after stop."""
    del config  # launch rules arrive on the start RPC
    prepare_runtime_dir()
    clear_stale_runtime()
    _write_pid()
    state = ServeState(config=LaunchConfig())
    sock = control_socket_path()
    sock.unlink(missing_ok=True)

    async def on_control(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _handle_control(reader, writer, state)

    server = await asyncio.start_unix_server(on_control, path=str(sock))
    apply_socket_perms(sock)
    try:
        await state.shutdown.wait()
    finally:
        await _stop_vm(state)
        server.close()
        await server.wait_closed()
        _unlink_runtime()


def start_daemon(config: LaunchConfig) -> None:
    """Spawn idle `corvus serve` (root/dev fallback) and RPC start."""
    if node_pid() is not None:
        rpc_start(config)
        return
    clear_stale_runtime()
    prepare_runtime_dir()
    log_path = node_log_path()
    cmd = [sys.executable, "-m", "corvus_node", "serve"]
    env = os.environ.copy()
    log = log_path.open("ab")
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    finally:
        log.close()
    deadline = time.monotonic() + READY_WAIT_SEC
    sock = control_socket_path()
    while time.monotonic() < deadline:
        if sock.exists():
            try:
                with ControlClient(sock) as client:
                    frame = client.rpc("status")
                if frame["type"] == "status_ok":
                    rpc_start(config)
                    return
            except ControlError:
                pass
        code = proc.poll()
        if code is not None:
            raise IsolationUnavailable(
                _start_failure(f"Node serve exited {code} before the control socket was ready")
            )
        time.sleep(START_POLL_SEC)
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    raise GuestBootTimeout(_start_failure("Node did not become ready in time"))


def _start_failure(prefix: str) -> str:
    log = node_log_path()
    detail = ""
    if log.is_file():
        try:
            detail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            detail = ""
    if not detail:
        return f"{prefix}\n--- node log ---\n(empty or missing: {log})"
    return f"{prefix}\n--- node log ---\n{detail}"


def rpc_status() -> dict:
    with ControlClient() as client:
        frame = client.rpc("status")
    if frame["type"] != "status_ok":
        raise ControlError(f"unexpected status reply: {frame['type']}")
    return frame["payload"]


def rpc_start(config: LaunchConfig) -> dict:
    payload = {
        "tools": sorted(config.allowed_tools),
        "workspace": list(config.workspace_paths),
    }
    with ControlClient() as client:
        frame = client.rpc("start", payload)
    if frame["type"] != "start_ok":
        raise ControlError(f"unexpected start reply: {frame['type']}")
    return frame["payload"]


def rpc_stop() -> None:
    with ControlClient() as client:
        frame = client.rpc("stop")
    if frame["type"] != "stop_ok":
        raise ControlError(f"unexpected stop reply: {frame['type']}")


def rpc_shutdown() -> None:
    with ControlClient() as client:
        frame = client.rpc("shutdown")
    if frame["type"] != "shutdown_ok":
        raise ControlError(f"unexpected shutdown reply: {frame['type']}")
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if node_pid() is None:
            return
        time.sleep(0.05)
