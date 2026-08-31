"""Launcher config and fail-closed checks (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

import os
from pathlib import Path

import pytest

from corvus_node.vm.launcher import (
    ROOT_INSTANCE_DIR,
    UNIX_PATH_MAX,
    IsolationUnavailable,
    build_jailer_argv,
    build_vm_config,
    ensure_runtime,
    instance_base_dir,
    jail_root,
    jailer_pid_path,
    jailer_uid,
    mount_forbids_device_nodes,
    pid_is_alive,
    read_pid_file,
    require_dev_nodes,
    require_root,
    require_unix_path,
    vsock_listen_path,
)


def test_vsock_listen_path() -> None:
    assert vsock_listen_path(Path("/tmp/v.sock"), 4040) == Path("/tmp/v.sock_4040")


def test_root_vsock_path_fits_unix() -> None:
    root = jail_root(ROOT_INSTANCE_DIR, "firecracker", "a" * 32)
    listen = vsock_listen_path(root / "v.sock", 4040)
    assert len(os.fsencode(listen)) <= UNIX_PATH_MAX
    require_unix_path(listen)


def test_legacy_nested_vsock_path_exceeds_unix() -> None:
    """The v0.1.3 first cut nested the uuid twice under XDG_RUNTIME_DIR."""
    nested = (
        Path("/run/user/1000/corvus-node")
        / ("a" * 32)
        / "jails"
        / "firecracker"
        / ("a" * 32)
        / "root"
        / "v.sock_4040"
    )
    assert len(os.fsencode(nested)) > UNIX_PATH_MAX
    with pytest.raises(IsolationUnavailable, match="AF_UNIX path too long"):
        require_unix_path(nested)


def test_instance_base_dir_root_uses_var_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("corvus_node.vm.launcher.os.geteuid", lambda: 0)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    assert instance_base_dir() == ROOT_INSTANCE_DIR


def test_require_dev_nodes_rejects_nodev(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Statvfs:
        f_flag = getattr(os, "ST_NODEV", 0x400)

    monkeypatch.setattr("corvus_node.vm.launcher.os.statvfs", lambda _p: _Statvfs())
    assert mount_forbids_device_nodes(tmp_path) is True
    with pytest.raises(IsolationUnavailable, match="nodev"):
        require_dev_nodes(tmp_path)


def test_require_unix_path_rejects_long() -> None:
    with pytest.raises(IsolationUnavailable, match="AF_UNIX"):
        require_unix_path(Path("/" + "a" * 200))


def test_build_vm_config_shape() -> None:
    cfg = build_vm_config(
        kernel=Path("/k/vmlinux"),
        rootfs=Path("/k/rootfs.ext4"),
        uds_path=Path("/tmp/v.sock"),
        guest_cid=3,
    )
    assert cfg["boot-source"]["kernel_image_path"] == "/k/vmlinux"
    assert "init=/opt/corvus/guest/init.sh" in cfg["boot-source"]["boot_args"]
    assert cfg["drives"][0]["path_on_host"] == "/k/rootfs.ext4"
    assert cfg["drives"][0]["is_root_device"] is True
    assert cfg["drives"][0]["is_read_only"] is True
    assert cfg["machine-config"]["vcpu_count"] == 1
    assert cfg["vsock"]["guest_cid"] == 3
    assert cfg["vsock"]["uds_path"] == "/tmp/v.sock"
    assert "network-interfaces" not in cfg
    assert "logger" not in cfg


def test_build_vm_config_jailed() -> None:
    cfg = build_vm_config(
        kernel=Path("/k/vmlinux"),
        rootfs=Path("/k/rootfs.ext4"),
        uds_path=Path("/tmp/v.sock"),
        jailed=True,
        log_path=Path("/fc.log"),
    )
    assert cfg["boot-source"]["kernel_image_path"] == "/vmlinux"
    assert cfg["drives"][0]["path_on_host"] == "/rootfs.ext4"
    assert cfg["vsock"]["uds_path"] == "/v.sock"
    assert cfg["logger"]["log_path"] == "/fc.log"


def test_jailer_argv_shape(tmp_path: Path) -> None:
    argv = build_jailer_argv(
        jailer_bin="/usr/bin/jailer",
        firecracker_bin="/usr/bin/firecracker",
        jail_id="abc123",
        uid=60123,
        gid=60123,
        chroot_base=tmp_path / "jails",
    )
    assert argv[0] == "/usr/bin/jailer"
    assert "--new-pid-ns" in argv
    assert "--cgroup-version" in argv
    assert any(item.startswith("memory.max=") for item in argv)
    assert "--config-file" in argv
    assert "/vm.json" in argv
    assert "/fc.sock" in argv


def test_jailer_pid_path() -> None:
    assert jailer_pid_path(Path("/j/root"), "firecracker") == Path("/j/root/firecracker.pid")


def test_read_pid_file(tmp_path: Path) -> None:
    path = tmp_path / "firecracker.pid"
    path.write_text("4321\n")
    assert read_pid_file(path) == 4321
    assert read_pid_file(tmp_path / "missing") is None


def test_pid_is_alive_self() -> None:
    assert pid_is_alive(os.getpid()) is True


def test_jailer_uid_stable() -> None:
    assert jailer_uid("same") == jailer_uid("same")
    assert 60000 <= jailer_uid("same") < 61000


def test_require_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("corvus_node.vm.launcher.os.geteuid", lambda: 1000)
    with pytest.raises(IsolationUnavailable, match="root"):
        require_root()


def test_build_vm_config_logger(tmp_path: Path) -> None:
    log = tmp_path / "fc.log"
    cfg = build_vm_config(
        kernel=Path("/k/vmlinux"),
        rootfs=Path("/k/rootfs.ext4"),
        uds_path=Path("/tmp/v.sock"),
        log_path=log,
    )
    assert cfg["logger"]["log_path"] == str(log)


def test_resolve_firecracker_uses_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CORVUS_NODE_FIRECRACKER", raising=False)
    monkeypatch.setattr("corvus_node.vm.launcher.shutil.which", lambda _name: None)
    monkeypatch.setattr("corvus_node.vm.launcher.DEFAULT_CACHE", tmp_path)
    binary = tmp_path / "firecracker"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    from corvus_node.vm.launcher import resolve_firecracker

    assert resolve_firecracker() == str(binary.resolve())


def test_ensure_runtime_fails_without_kernel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    with pytest.raises(IsolationUnavailable):
        ensure_runtime()
