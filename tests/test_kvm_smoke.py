"""KVM smoke against the installed Node. Opt-in; skipped by `make test`.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

from corvus_node.cli import main
from corvus_node.node.control import ControlError, node_pid
from corvus_node.node.daemon import rpc_status

_SKIP_NO_SMOKE = "set CORVUS_NODE_SMOKE=1 after ./install.sh (no sudo for the tests)"
_SKIP_NO_NODE = "Node service is not running; ./install.sh, then CORVUS_NODE_SMOKE=1"
_SKIP_VM_BUSY = "guest VM is already running; corvus vm stop first"


def _installed_smoke_ready() -> tuple[bool, str]:
    if os.environ.get("CORVUS_NODE_SMOKE", "").strip() != "1":
        return False, _SKIP_NO_SMOKE
    if node_pid() is None:
        return False, _SKIP_NO_NODE
    try:
        snap = rpc_status()
    except ControlError as exc:
        return False, f"Node control failed: {exc}"
    if snap.get("state") == "running":
        return False, _SKIP_VM_BUSY
    return True, ""


_READY, _SKIP_REASON = _installed_smoke_ready()

pytestmark = pytest.mark.skipif(not _READY, reason=_SKIP_REASON)


@pytest.fixture(autouse=True)
def use_installed_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep XDG isolation; talk to the installed Node socket."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("CORVUS_NODE_SKIP_UPDATE_CHECK", "1")
    monkeypatch.delenv("CORVUS_NODE_RUNTIME_DIR", raising=False)


@pytest.fixture(autouse=True)
def _reap_guest_vm() -> None:
    yield
    main(["vm", "stop", "--yes"])


def test_run_once_stub_turn(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "--once", "hello"])
    assert code == 0
    assert "Stub LLM response" in capsys.readouterr().out


def test_run_once_echo_after_allow(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "--once", "--tools", "echo", "hello"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Stub LLM after tools" in out
    assert "Hello from echo" in out


def test_run_once_file_write(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("old\n", encoding="utf-8")
    code = main(
        [
            "run",
            "--once",
            "--tools",
            "file_write",
            "--workspace",
            str(tmp_path),
            "edit notes.txt to 'reviewed'",
        ]
    )
    assert code == 0
    assert "Stub LLM after tools" in capsys.readouterr().out
    assert notes.read_text(encoding="utf-8") == "reviewed"


def test_run_once_file_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "hello.txt").write_text("workspace hello\n", encoding="utf-8")
    code = main(
        [
            "run",
            "--once",
            "--tools",
            "file_read",
            "--workspace",
            str(tmp_path),
            "hello",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Stub LLM after tools" in out
    assert "workspace hello" in out


def test_run_once_reviews_live_host_edit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("first draft\n", encoding="utf-8")
    code = main(
        [
            "run",
            "--once",
            "--tools",
            "file_read",
            "--workspace",
            str(tmp_path),
            "review notes.txt",
        ]
    )
    assert code == 0
    assert "first draft" in capsys.readouterr().out
    notes.write_text("user edited\n", encoding="utf-8")
    code = main(
        [
            "run",
            "--once",
            "--tools",
            "file_read",
            "--workspace",
            str(tmp_path),
            "review notes.txt",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "user edited" in out
    assert "first draft" not in out


def test_vm_start_status_chat_stop(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["vm", "start"])
    assert code == 0
    code = main(["vm", "status"])
    assert code == 0
    status = capsys.readouterr().out
    assert "VM: running" in status
    monkeypatch.setattr(sys, "stdin", io.StringIO("hello\nhello again\n/exit\n"))
    code = main(["chat"])
    assert code == 0
    out = capsys.readouterr().out
    assert "hello" in out
    assert "hello again" in out
    code = main(["status"])
    assert code == 0
    full = capsys.readouterr().out
    assert "Node: up" in full
    assert "VM: running" in full
    code = main(["vm", "stop", "--yes"])
    assert code == 0
    code = main(["vm", "status"])
    assert code == 0
    assert "VM: idle" in capsys.readouterr().out
