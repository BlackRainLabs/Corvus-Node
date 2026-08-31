"""Host AF_UNIX operator control. Not guest envelopes; not vsock.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Any

from corvus_node.vm.launcher import pid_is_alive, read_pid_file

CONTROL_SOCK_NAME = "control.sock"
PID_NAME = "node.pid"
LOG_NAME = "node.log"
CONTROL_GROUP = "corvus"
INSTALL_HINT = "Corvus-Node is not running; ./install.sh"


def product_prefix() -> Path:
    env = os.environ.get("CORVUS_NODE_PREFIX", "").strip()
    if env:
        return Path(env)
    return Path.home() / "Corvus-Node"


def runtime_dir() -> Path:
    env = os.environ.get("CORVUS_NODE_RUNTIME_DIR", "").strip()
    if env:
        return Path(env)
    return product_prefix() / "run"


class ControlError(RuntimeError):
    """Operator control socket failed or returned an error frame."""

    def __init__(self, message: str, *, code: str = "control") -> None:
        super().__init__(message)
        self.code = code


def control_socket_path() -> Path:
    return runtime_dir() / CONTROL_SOCK_NAME


def pid_file_path() -> Path:
    return runtime_dir() / PID_NAME


def node_log_path() -> Path:
    return runtime_dir() / LOG_NAME


def prepare_runtime_dir() -> Path:
    path = runtime_dir()
    path.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        os.chmod(path, 0o750)
        gid = _control_gid()
        if gid is not None:
            os.chown(path, 0, gid)
    else:
        os.chmod(path, 0o700)
    return path


def apply_socket_perms(path: Path) -> None:
    os.chmod(path, 0o660)
    _chown_control_group(path, 0 if os.geteuid() == 0 else os.getuid())


def apply_pid_perms(path: Path) -> None:
    os.chmod(path, 0o640)
    if os.geteuid() == 0:
        _chown_control_group(path, 0)


def _chown_control_group(path: Path, uid: int) -> None:
    gid = _control_gid()
    if gid is None:
        return
    try:
        os.chown(path, uid, gid)
    except PermissionError:
        pass


def _control_gid() -> int | None:
    try:
        import grp

        return grp.getgrnam(CONTROL_GROUP).gr_gid
    except KeyError:
        return None


def encode_frame(type_: str, payload: dict[str, Any] | None = None) -> bytes:
    body = {"type": type_, "payload": payload or {}}
    return (json.dumps(body, separators=(",", ":")) + "\n").encode("utf-8")


async def write_frame(
    writer: asyncio.StreamWriter,
    type_: str,
    payload: dict[str, Any] | None = None,
) -> None:
    writer.write(encode_frame(type_, payload))
    await writer.drain()


async def read_frame(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    line = await reader.readline()
    if not line:
        return None
    return decode_frame(line)


def decode_frame(line: str | bytes) -> dict[str, Any]:
    if isinstance(line, bytes):
        text = line.decode("utf-8")
    else:
        text = line
    text = text.strip()
    if not text:
        raise ControlError("empty control frame", code="codec")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ControlError(f"invalid control JSON: {exc}", code="codec") from exc
    if not isinstance(data, dict) or not isinstance(data.get("type"), str) or not data["type"]:
        raise ControlError("control frame missing type", code="codec")
    payload = data.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ControlError("control payload must be an object", code="codec")
    return {"type": data["type"], "payload": payload}


def node_pid() -> int | None:
    pid = read_pid_file(pid_file_path())
    if pid is not None and pid_is_alive(pid):
        return pid
    if control_socket_up():
        return pid if pid is not None else 0
    return None


def control_socket_up() -> bool:
    path = control_socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        sock.connect(os.fsdecode(path))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def clear_stale_runtime() -> None:
    if node_pid() is not None:
        return
    control_socket_path().unlink(missing_ok=True)
    pid_file_path().unlink(missing_ok=True)


class ControlClient:
    """Blocking operator client (CLI). One connection per command or chat attach."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or control_socket_path()
        self._sock: socket.socket | None = None
        self._buf = b""

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(os.fsdecode(self.path))
        except OSError as exc:
            sock.close()
            raise ControlError(
                INSTALL_HINT,
                code="not_running",
            ) from exc
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            self._buf = b""

    def __enter__(self) -> ControlClient:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def send(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        if self._sock is None:
            raise ControlError("not connected", code="not_running")
        self._sock.sendall(encode_frame(type_, payload))

    def read(self) -> dict[str, Any]:
        if self._sock is None:
            raise ControlError("not connected", code="not_running")
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ControlError("control socket closed", code="closed")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        frame = decode_frame(line)
        if frame["type"] == "error":
            reason = str(frame["payload"].get("reason") or "control error")
            code = str(frame["payload"].get("code") or "control")
            raise ControlError(reason, code=code)
        return frame

    def rpc(self, type_: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.send(type_, payload)
        return self.read()
