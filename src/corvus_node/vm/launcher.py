"""Firecracker launch via jailer. Fail closed when isolation is unavailable.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import shutil
import signal
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from corvus_node.audit.store import JsonlAuditStore
from corvus_node.node.session import LaunchConfig, NodeSession
from corvus_node.vm.checksums import (
    FIRECRACKER_BIN_SHA256,
    JAILER_BIN_SHA256,
    KERNEL_SHA256,
    verify_sha256,
)

KVM_PATH = Path("/dev/kvm")
DEFAULT_CACHE = Path(".cache/corvus-node")
DEFAULT_KERNEL = DEFAULT_CACHE / "vmlinux"
DEFAULT_ROOTFS = DEFAULT_CACHE / "rootfs.ext4"
DEFAULT_VSOCK_PORT = 4040
DEFAULT_GUEST_CID = 3
DEFAULT_MEM_MIB = 512
TURN_TIMEOUT_SEC = 90.0
GUEST_INIT = "/opt/corvus/guest/init.sh"
BOOT_ARGS = f"console=ttyS0 reboot=k panic=1 pci=off nomodules root=/dev/vda ro init={GUEST_INIT}"
JAILER_UID_BASE = 60000
JAILER_UID_SPAN = 1000
CGROUP_PIDS_MAX = 128
# Linux sockaddr_un.sun_path is 108 bytes including the trailing NUL.
UNIX_PATH_MAX = 107
ROOT_INSTANCE_DIR = Path("/var/lib/corvus-node")
JAILED_UDS = Path("/v.sock")
# Jailer --new-pid-ns clone()s Firecracker then the parent exits 0.
FC_PID_WAIT_SEC = 15.0


class IsolationUnavailable(RuntimeError):
    """KVM, vsock, jailer, Firecracker, kernel, or rootfs is missing. No fallback."""


class GuestBootTimeout(RuntimeError):
    """The guest did not complete a turn before the host timeout."""


@dataclass(frozen=True)
class RuntimeAssets:
    firecracker_bin: str
    jailer_bin: str
    kernel: Path
    rootfs: Path
    vsock_port: int = DEFAULT_VSOCK_PORT
    guest_cid: int = DEFAULT_GUEST_CID


def vsock_listen_path(uds_path: Path, port: int) -> Path:
    """Host UDS Firecracker connects to for guest-initiated vsock to CID 2."""
    return Path(f"{uds_path}_{port}")


def require_unix_path(path: Path) -> Path:
    """Fail closed when a UDS path cannot fit in sockaddr_un."""
    encoded = os.fsencode(path)
    if len(encoded) > UNIX_PATH_MAX:
        raise IsolationUnavailable(
            f"AF_UNIX path too long ({len(encoded)} > {UNIX_PATH_MAX} bytes): {path}"
        )
    return path


def jailer_uid(instance_id: str) -> int:
    n = int(hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:8], 16)
    return JAILER_UID_BASE + (n % JAILER_UID_SPAN)


def jail_dir(chroot_base: Path, exec_name: str, jail_id: str) -> Path:
    return chroot_base / exec_name / jail_id


def jail_root(chroot_base: Path, exec_name: str, jail_id: str) -> Path:
    return jail_dir(chroot_base, exec_name, jail_id) / "root"


def jailer_pid_path(root: Path, exec_name: str) -> Path:
    """Host-visible PID of the jailed Firecracker (`<exec_name>.pid` in the jail root)."""
    return root / f"{exec_name}.pid"


def read_pid_file(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip().split()[0]
    except OSError:
        return None
    if raw.isdigit():
        return int(raw)
    return None


def pid_is_alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").is_dir()


def chown_mode(path: Path, uid: int, gid: int, mode: int) -> None:
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def build_jailer_argv(
    *,
    jailer_bin: str,
    firecracker_bin: str,
    jail_id: str,
    uid: int,
    gid: int,
    chroot_base: Path,
    mem_mib: int = DEFAULT_MEM_MIB,
) -> list[str]:
    mem_bytes = mem_mib * 1024 * 1024
    return [
        jailer_bin,
        "--id",
        jail_id,
        "--exec-file",
        firecracker_bin,
        "--uid",
        str(uid),
        "--gid",
        str(gid),
        "--chroot-base-dir",
        str(chroot_base),
        "--new-pid-ns",
        "--cgroup-version",
        "2",
        "--cgroup",
        f"memory.max={mem_bytes}",
        "--cgroup",
        f"pids.max={CGROUP_PIDS_MAX}",
        "--",
        "--config-file",
        "/vm.json",
        "--api-sock",
        "/fc.sock",
    ]


def resolve_kernel(kernel: Path | None = None) -> Path:
    if kernel is not None:
        return kernel
    env = os.environ.get("CORVUS_NODE_KERNEL", "").strip()
    if env:
        return Path(env)
    return DEFAULT_KERNEL


def resolve_rootfs(rootfs: Path | None = None) -> Path:
    if rootfs is not None:
        return rootfs
    env = os.environ.get("CORVUS_NODE_ROOTFS", "").strip()
    if env:
        return Path(env)
    return DEFAULT_ROOTFS


def resolve_firecracker(firecracker_bin: str | None = None) -> str | None:
    if firecracker_bin:
        return firecracker_bin
    env = os.environ.get("CORVUS_NODE_FIRECRACKER", "").strip()
    if env:
        return env
    which = shutil.which("firecracker")
    if which:
        return which
    cached = DEFAULT_CACHE / "firecracker"
    if cached.is_file():
        return str(cached.resolve())
    return None


def resolve_jailer(jailer_bin: str | None = None) -> str | None:
    if jailer_bin:
        return jailer_bin
    env = os.environ.get("CORVUS_NODE_JAILER", "").strip()
    if env:
        return env
    which = shutil.which("jailer")
    if which:
        return which
    cached = DEFAULT_CACHE / "jailer"
    if cached.is_file():
        return str(cached.resolve())
    return None


def resolve_vsock_port() -> int:
    raw = os.environ.get("CORVUS_NODE_VSOCK_PORT", "").strip()
    if raw:
        return int(raw)
    return DEFAULT_VSOCK_PORT


def mount_forbids_device_nodes(path: Path) -> bool:
    """True when the mount has nodev (jailer mknod of /dev/kvm would be unusable)."""
    try:
        flags = os.statvfs(path).f_flag
    except OSError:
        return False
    nodev = getattr(os, "ST_NODEV", 0x400)
    return bool(flags & nodev)


def require_dev_nodes(path: Path) -> None:
    if mount_forbids_device_nodes(path):
        raise IsolationUnavailable(
            f"jail chroot {path} is on a nodev mount; jailer cannot open /dev/kvm"
        )


def instance_base_dir() -> Path:
    """Jail chroot-base on a non-nodev filesystem. /run and /tmp are typically nodev."""
    if os.geteuid() == 0:
        return ROOT_INSTANCE_DIR
    runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if runtime:
        return Path(runtime) / "corvus-node"
    return ROOT_INSTANCE_DIR


def audit_dir() -> Path:
    state = os.environ.get("XDG_STATE_HOME", "").strip()
    if state:
        return Path(state) / "corvus-node" / "audit"
    return Path.home() / ".local" / "state" / "corvus-node" / "audit"


def require_root() -> None:
    if os.geteuid() != 0:
        raise IsolationUnavailable("jailer launch requires root (euid 0); no raw Firecracker")


def _arch() -> str:
    machine = platform.machine()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    raise IsolationUnavailable(f"unsupported architecture {machine}")


def _verify_rootfs(rootfs: Path) -> None:
    sidecar = Path(str(rootfs) + ".sha256")
    if not sidecar.is_file():
        raise IsolationUnavailable(f"missing rootfs checksum sidecar: {sidecar}")
    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    try:
        verify_sha256(rootfs, expected, name="rootfs")
    except ValueError as exc:
        raise IsolationUnavailable(str(exc)) from exc


def build_vm_config(
    *,
    kernel: Path,
    rootfs: Path,
    uds_path: Path,
    guest_cid: int = DEFAULT_GUEST_CID,
    mem_size_mib: int = DEFAULT_MEM_MIB,
    log_path: Path | None = None,
    jailed: bool = False,
) -> dict:
    """Firecracker --config-file body. No TAP. jailed paths are in-chroot."""
    if jailed:
        kernel_s = "/vmlinux"
        rootfs_s = "/rootfs.ext4"
        uds_s = str(JAILED_UDS)
        log_s = "/fc.log"
    else:
        kernel_s = str(kernel)
        rootfs_s = str(rootfs)
        uds_s = str(uds_path)
        log_s = str(log_path) if log_path is not None else ""
    cfg: dict = {
        "boot-source": {
            "kernel_image_path": kernel_s,
            "boot_args": BOOT_ARGS,
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": rootfs_s,
                "is_root_device": True,
                "is_read_only": True,
            }
        ],
        "machine-config": {
            "vcpu_count": 1,
            "mem_size_mib": mem_size_mib,
            "smt": False,
        },
        "vsock": {
            "vsock_id": "vsock0",
            "guest_cid": guest_cid,
            "uds_path": uds_s,
        },
    }
    if log_path is not None:
        cfg["logger"] = {
            "log_path": log_s or str(log_path),
            "level": "Info",
            "show_level": True,
            "show_log_origin": True,
        }
    return cfg


def stage_jail_root(
    root: Path,
    *,
    kernel: Path,
    rootfs: Path,
    config: dict,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    _place(kernel, root / "vmlinux")
    _place(rootfs, root / "rootfs.ext4")
    (root / "vm.json").write_text(json.dumps(config, indent=2) + "\n")
    (root / "fc.log").touch()
    os.chmod(root / "vm.json", 0o600)
    os.chmod(root / "fc.log", 0o600)


def _place(src: Path, dest: Path) -> None:
    dest.unlink(missing_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def ensure_runtime(
    *,
    kernel: Path | None = None,
    rootfs: Path | None = None,
    firecracker_bin: str | None = None,
    jailer_bin: str | None = None,
) -> RuntimeAssets:
    """Require a real microVM path. Never fall back to TCP or in-process run."""
    if not hasattr(__import__("socket"), "AF_VSOCK"):
        raise IsolationUnavailable("AF_VSOCK is not available on this Python/OS")
    if not KVM_PATH.exists():
        raise IsolationUnavailable(f"{KVM_PATH} is missing; Corvus-Node requires KVM")
    arch = _arch()
    binary = resolve_firecracker(firecracker_bin)
    if not binary or not Path(binary).is_file():
        raise IsolationUnavailable(
            "firecracker binary not found; run `make guest-assets` or set CORVUS_NODE_FIRECRACKER"
        )
    if not os.access(binary, os.X_OK):
        raise IsolationUnavailable(f"firecracker is not executable: {binary}")
    jailer = resolve_jailer(jailer_bin)
    if not jailer or not Path(jailer).is_file():
        raise IsolationUnavailable(
            "jailer binary not found; run `make guest-assets` or set CORVUS_NODE_JAILER"
        )
    if not os.access(jailer, os.X_OK):
        raise IsolationUnavailable(f"jailer is not executable: {jailer}")
    kernel_path = resolve_kernel(kernel)
    if not kernel_path.is_file():
        raise IsolationUnavailable(
            "set CORVUS_NODE_KERNEL or run `make guest-assets` (see guest/README.md)"
        )
    rootfs_path = resolve_rootfs(rootfs)
    if not rootfs_path.is_file():
        raise IsolationUnavailable(
            "set CORVUS_NODE_ROOTFS or run `make guest-assets` (see guest/README.md)"
        )
    try:
        verify_sha256(kernel_path, KERNEL_SHA256[arch], name="kernel")
        verify_sha256(Path(binary), FIRECRACKER_BIN_SHA256[arch], name="firecracker")
        verify_sha256(Path(jailer), JAILER_BIN_SHA256[arch], name="jailer")
    except ValueError as exc:
        raise IsolationUnavailable(str(exc)) from exc
    _verify_rootfs(rootfs_path)
    return RuntimeAssets(
        firecracker_bin=binary,
        jailer_bin=jailer,
        kernel=kernel_path,
        rootfs=rootfs_path,
        vsock_port=resolve_vsock_port(),
    )


def probe_isolation() -> list[str]:
    """Asset gaps that would make the Node service fail closed. Safe without root."""
    gaps: list[str] = []
    try:
        ensure_runtime()
    except IsolationUnavailable as exc:
        gaps.append(str(exc))
    return gaps


def _tail_text(path: Path, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:]


def _boot_failure_detail(prefix: str, log_path: Path) -> str:
    parts = [prefix]
    log = _tail_text(log_path)
    parts.append("--- firecracker log ---")
    parts.append(log or f"(empty or missing: {log_path})")
    serial = _tail_text(log_path.parent / "serial.log")
    if serial:
        parts.append("--- guest serial ---")
        parts.append(serial)
    return "\n".join(parts)


async def launch_turn(config: LaunchConfig) -> str:
    """Boot jailed Firecracker, serve Node on vsock, return agent_response text."""
    require_root()
    assets = ensure_runtime()
    instance_id = uuid4().hex
    config.vm_instance_id = instance_id
    config.guest_cid = assets.guest_cid
    chroot_base = instance_base_dir()
    chroot_base.mkdir(parents=True, exist_ok=True)
    os.chmod(chroot_base, 0o700)
    require_dev_nodes(chroot_base)
    exec_name = Path(assets.firecracker_bin).name
    instance = jail_dir(chroot_base, exec_name, instance_id)
    proc: asyncio.subprocess.Process | None = None
    server: asyncio.AbstractServer | None = None
    watcher: asyncio.Task[None] | None = None
    fc_watcher: asyncio.Task[None] | None = None
    fc_pid: int | None = None
    log_path = instance / "fc.log"
    try:
        uid = jailer_uid(instance_id)
        root = jail_root(chroot_base, exec_name, instance_id)
        payload = build_vm_config(
            kernel=assets.kernel.resolve(),
            rootfs=assets.rootfs.resolve(),
            uds_path=JAILED_UDS,
            guest_cid=assets.guest_cid,
            log_path=Path("/fc.log"),
            jailed=True,
        )
        stage_jail_root(
            root,
            kernel=assets.kernel.resolve(),
            rootfs=assets.rootfs.resolve(),
            config=payload,
        )
        log_path = root / "fc.log"
        listen_path = require_unix_path(
            vsock_listen_path(root / JAILED_UDS.name, assets.vsock_port)
        )
        argv = build_jailer_argv(
            jailer_bin=assets.jailer_bin,
            firecracker_bin=assets.firecracker_bin,
            jail_id=instance_id,
            uid=uid,
            gid=uid,
            chroot_base=chroot_base,
        )

        loop = asyncio.get_running_loop()
        done: asyncio.Future[str] = loop.create_future()
        audit_path = audit_dir() / f"{instance_id}.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        async def on_guest(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            session = NodeSession(config, audit=JsonlAuditStore(audit_path))
            try:
                text = await session.serve(reader, writer)
                if not done.done():
                    done.set_result(text)
            except Exception as exc:
                if not done.done():
                    done.set_exception(exc)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        try:
            server = await asyncio.start_unix_server(on_guest, path=str(listen_path))
        except OSError as exc:
            raise IsolationUnavailable(f"failed to bind vsock UDS {listen_path}: {exc}") from exc
        # Jailer drops to uid/gid before exec. Config, log, and the vsock UDS
        # must be owned by that user (directory chown does not cover these files).
        chown_mode(root / "vm.json", uid, uid, 0o600)
        chown_mode(root / "fc.log", uid, uid, 0o600)
        chown_mode(listen_path, uid, uid, stat.S_IRUSR | stat.S_IWUSR)
        serial_path = root / "serial.log"
        serial_path.touch()
        chown_mode(serial_path, uid, uid, 0o600)

        # Keep guest ttyS0 off the operator TTY. Inherited stdin made chat
        # see EOF after handshake; kernel dmesg buried the REPL.
        serial = serial_path.open("wb")
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(chroot_base),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=serial,
                stderr=serial,
            )
        finally:
            serial.close()
        pid_path = jailer_pid_path(root, exec_name)

        async def watch_jailer() -> None:
            assert proc is not None
            code = await proc.wait()
            # --new-pid-ns: parent jailer exits 0 after clone(); Firecracker continues.
            if code != 0 and not done.done():
                done.set_exception(GuestBootTimeout(f"jailer exited {code} before turn completed"))

        async def watch_firecracker() -> None:
            nonlocal fc_pid
            deadline = loop.time() + FC_PID_WAIT_SEC
            while fc_pid is None and loop.time() < deadline:
                fc_pid = read_pid_file(pid_path)
                if fc_pid is not None:
                    break
                if proc.returncode not in (None, 0):
                    return
                await asyncio.sleep(0.05)
            if fc_pid is None:
                if not done.done():
                    done.set_exception(
                        GuestBootTimeout(
                            _boot_failure_detail(f"jailer did not write {pid_path.name}", log_path)
                        )
                    )
                return
            while pid_is_alive(fc_pid):
                await asyncio.sleep(0.1)
            if not done.done():
                done.set_exception(
                    GuestBootTimeout(
                        _boot_failure_detail(
                            f"firecracker pid {fc_pid} exited before turn completed",
                            log_path,
                        )
                    )
                )

        watcher = asyncio.create_task(watch_jailer())
        fc_watcher = asyncio.create_task(watch_firecracker())
        try:
            if config.once:
                result = await asyncio.wait_for(asyncio.shield(done), timeout=TURN_TIMEOUT_SEC)
            else:
                result = await asyncio.shield(done)
        except TimeoutError as exc:
            raise GuestBootTimeout(
                _boot_failure_detail(
                    f"guest did not complete a turn within {int(TURN_TIMEOUT_SEC)}s",
                    log_path,
                )
            ) from exc
        except GuestBootTimeout as exc:
            raise GuestBootTimeout(_boot_failure_detail(str(exc), log_path)) from exc
        return result
    finally:
        if config.prompts is not None:
            try:
                config.prompts.put_nowait(None)
            except Exception:
                pass
        if watcher is not None:
            watcher.cancel()
            try:
                await watcher
            except (asyncio.CancelledError, Exception):
                pass
        if fc_watcher is not None:
            fc_watcher.cancel()
            try:
                await fc_watcher
            except (asyncio.CancelledError, Exception):
                pass
        reap = (
            fc_pid if fc_pid is not None else read_pid_file(instance / "root" / f"{exec_name}.pid")
        )
        if reap is not None:
            try:
                os.kill(reap, signal.SIGKILL)
            except OSError:
                pass
            for _ in range(50):
                if not pid_is_alive(reap):
                    break
                await asyncio.sleep(0.05)
        if proc is not None and proc.returncode is None:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                pass
        if server is not None:
            server.close()
            await server.wait_closed()
        shutil.rmtree(instance, ignore_errors=True)
