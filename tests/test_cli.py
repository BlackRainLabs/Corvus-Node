"""CLI fails closed without Firecracker/KVM. Operator verbs without a VM.

Organization: Black Rain Labs
Division: Research & Development Division
"""

import io
import sys
from pathlib import Path

import pytest

from corvus_node import __version__
from corvus_node.cli import main
from corvus_node.node.info import format_runtime_status, format_vm_status


def test_run_once_fails_closed_without_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    code = main(["run", "--once", "hello"])
    assert code == 2


def test_workspace_flag_without_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    code = main(["run", "--once", "hello", "--workspace", str(tmp_path)])
    assert code == 2
    err = capsys.readouterr().err
    assert "not mounted" not in err
    assert "install.sh" in err or "isolation unavailable" in err


def test_two_workspace_flags_fail_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    code = main(["run", "--once", "hello", "--workspace", str(tmp_path), "--workspace", str(other)])
    assert code == 2
    err = capsys.readouterr().err
    assert "one --workspace path" in err


def test_missing_workspace_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "--once", "hello", "--workspace", str(tmp_path / "missing")])
    assert code == 2
    assert "missing" in capsys.readouterr().err


def test_once_tools_before_text_parses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    code = main(["run", "--once", "--tools", "echo", "hello"])
    assert code == 2


def test_start_fails_closed_without_node(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["start"])
    assert code == 2
    assert "install.sh" in capsys.readouterr().err


def test_chat_fails_closed_when_node_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["chat"])
    assert code == 2
    assert "not running" in capsys.readouterr().err


def test_stop_already_down_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["stop"])
    assert code == 0
    assert "already stopped" in capsys.readouterr().err


def test_format_runtime_status_splits_node_and_vm() -> None:
    assert format_runtime_status(None, None) == ["Node: down", "VM: (none)"]
    idle = format_runtime_status(3, {"state": "idle", "pid": 3, "vm_instance_id": ""})
    assert idle[0] == "Node: up  pid=3"
    assert idle[1] == "VM: idle"
    running = format_vm_status(
        {
            "state": "running",
            "vm_instance_id": "abc",
            "tools": ["echo"],
            "workspace": ["/tmp/ws"],
        }
    )
    assert running[0] == "VM: running  id=abc"
    assert "echo" in running[1]
    assert "/tmp/ws" in running[2]


def test_run_without_once_fails(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "hello"])
    assert code == 2
    assert "run --once TEXT" in capsys.readouterr().err


def test_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Corvus-Node" in out
    assert "usage: corvus" in out
    assert "Not yet" in out
    assert "live AI model" in out
    assert "vm start" in out
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_status_without_node(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "Node: down" in out
    assert "VM: (none)" in out
    assert "This preview:" in out
    assert "Not yet:" in out
    assert "Version:" in out
    assert "Isolation:" in out
    assert out.index("Node: down") < out.index("This preview:")
    assert out.index("This preview:") < out.index("Version:")
    assert out.index("Version:") < out.index("Isolation:")


def test_settings_roundtrip_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path / "run"))
    ws = tmp_path / "ws"
    ws.mkdir()
    assert main(["settings", "set", "tools", "echo,file_read"]) == 0
    assert main(["settings", "set", "workspace", str(ws)]) == 0
    capsys.readouterr()
    assert main(["settings"]) == 0
    out = capsys.readouterr().out
    assert "echo" in out
    assert "file_read" in out
    assert str(ws.resolve()) in out
    assert main(["settings", "unset", "tools"]) == 0
    capsys.readouterr()
    assert main(["settings"]) == 0
    assert "(none)" in capsys.readouterr().out


def test_chat_live_until_exit(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("hello\n/exit\n"))
    assert main(["chat"]) == 0
    captured = capsys.readouterr()
    assert "reply:hello" in captured.out
    assert "you" in captured.err
    assert "/exit to leave" in captured.err
    assert "model: stub" in captured.err
    assert "context: —" in captured.err
    assert "stdin closed" not in captured.err


def test_chat_exit_sends_nothing(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("/exit\n"))
    assert main(["chat"]) == 0
    captured = capsys.readouterr()
    assert "reply:" not in captured.out
    assert "/exit to leave" in captured.err


def test_chat_empty_stdin_reports_closed(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert main(["chat"]) == 0
    assert "stdin closed" in capsys.readouterr().err


def test_vm_fails_closed_without_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["vm"])
    assert code == 2
    assert "vm start|stop|status" in capsys.readouterr().err


def test_vm_status_fails_closed_without_node(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["vm", "status"])
    assert code == 2
    captured = capsys.readouterr()
    assert "VM: (none)" in captured.out
    assert "install.sh" in captured.err


def test_vm_stop_fails_closed_when_node_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["vm", "stop"])
    assert code == 2
    err = capsys.readouterr().err
    assert "install.sh" in err or "not running" in err


def test_vm_start_fails_closed_without_node(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    code = main(["vm", "start"])
    assert code == 2
    assert "install.sh" in capsys.readouterr().err


def test_status_splits_node_and_vm(fake_node: object, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "Node: up" in out
    assert "VM: running" in out
    assert main(["vm", "status"]) == 0
    vm = capsys.readouterr().out
    assert "VM: running" in vm
    assert "Node:" not in vm


def test_status_brief_is_node_and_vm_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CORVUS_NODE_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CORVUS_NODE_KERNEL", str(tmp_path / "missing-kernel"))
    monkeypatch.setenv("CORVUS_NODE_ROOTFS", str(tmp_path / "missing-rootfs"))
    assert main(["status", "--brief"]) == 0
    out = capsys.readouterr().out
    assert "Node: down" in out
    assert "VM: (none)" in out
    assert "This preview:" not in out
    assert "Version:" not in out
    assert "Isolation:" not in out


def test_vm_start_via_control_socket(fake_node: object, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["vm", "start"]) == 0
    assert "started" in capsys.readouterr().err


def test_start_via_control_socket(fake_node: object, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["start"]) == 0
    assert "started" in capsys.readouterr().err


class _TtyStdin(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_vm_stop_shuts_down_guest_only(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "corvus_node.cli.rpc_shutdown",
        lambda: (_ for _ in ()).throw(AssertionError("vm stop must not shut down Node")),
    )
    assert main(["vm", "stop", "--yes"]) == 0
    err = capsys.readouterr().err
    assert "agent session only" in err
    assert "agent session ended" in err
    assert "Corvus stays ready" in err


def test_vm_stop_cancelled(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin("n\n"))
    assert main(["vm", "stop"]) == 2
    assert "cancelled" in capsys.readouterr().err


def test_vm_stop_requires_yes_when_not_a_tty(
    fake_node: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["vm", "stop"]) == 2
    assert "--yes" in capsys.readouterr().err


def test_stop_shuts_down_guest_and_node(
    fake_node: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["stop", "--yes"]) == 0
    err = capsys.readouterr().err
    assert "shut Corvus down" in err
    assert "agent session ended" in err
    assert "Corvus stopped" in err


def test_stop_cancelled(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin("n\n"))
    assert main(["stop"]) == 2
    assert "cancelled" in capsys.readouterr().err


def test_stop_accepted_on_tty(
    fake_node: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin("yes\n"))
    assert main(["stop"]) == 0
    err = capsys.readouterr().err
    assert "Corvus stopped" in err


def test_stop_does_not_stop_host_systemd(
    fake_node: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[int] = []
    monkeypatch.setattr(
        "corvus_node.cli._stop_systemd_unit",
        lambda: called.append(1) or 0,
    )
    assert main(["stop", "--yes"]) == 0
    assert called == []
    capsys.readouterr()


def test_update_skips_when_unreleased_or_unchecked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["update"]) == 0
    captured = capsys.readouterr()
    assert "Version:" in captured.out
    assert "Update:" in captured.out
    assert "installing" not in captured.err


def test_update_pips_when_github_newer_on_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from corvus_node.node.update import VersionStatus

    monkeypatch.setattr(
        "corvus_node.cli.check_version",
        lambda: VersionStatus("0.1.4", "0.1.5", "release", True, "GitHub 0.1.5 is newer"),
    )
    pip_refs: list[str] = []
    monkeypatch.setattr("corvus_node.cli._pip_upgrade", lambda ref: pip_refs.append(ref) or 0)
    monkeypatch.setattr("corvus_node.cli._start_systemd_unit", lambda: 0)
    assert main(["update"]) == 0
    assert pip_refs
    err = capsys.readouterr().err
    assert "installing" in err
    assert "updated" in err


def test_update_requires_yes_when_node_is_up(
    fake_node: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from corvus_node.node.update import VersionStatus

    monkeypatch.setattr(
        "corvus_node.cli.check_version",
        lambda: VersionStatus("0.1.4", "0.1.5", "release", True, "GitHub 0.1.5 is newer"),
    )
    pip_refs: list[str] = []
    monkeypatch.setattr("corvus_node.cli._pip_upgrade", lambda ref: pip_refs.append(ref) or 0)
    assert main(["update"]) == 2
    assert pip_refs == []
    err = capsys.readouterr().err
    assert "already running" in err
    assert "--yes" in err or "cancelled" in err


def test_update_yes_stops_live_node_then_pips(
    fake_node: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from corvus_node.node.update import VersionStatus

    monkeypatch.setattr(
        "corvus_node.cli.check_version",
        lambda: VersionStatus("0.1.4", "0.1.5", "release", True, "GitHub 0.1.5 is newer"),
    )
    pip_refs: list[str] = []
    monkeypatch.setattr("corvus_node.cli._pip_upgrade", lambda ref: pip_refs.append(ref) or 0)
    monkeypatch.setattr("corvus_node.cli._start_systemd_unit", lambda: 0)
    assert main(["update", "--yes"]) == 0
    assert pip_refs
    err = capsys.readouterr().err
    assert "already running" in err
    assert "Corvus stopped" in err
    assert "installing" in err
    assert "updated" in err
