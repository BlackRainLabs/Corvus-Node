"""Guided ./install.sh (no sudo, no KVM required).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "operator-install.sh"
WRAPPER = ROOT / "install.sh"


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged["CORVUS_NODE_SKIP_UPDATE_CHECK"] = "1"
    return subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_privileged_install_puts_corvus_on_usr_local_bin() -> None:
    text = (ROOT / "packaging" / "install.sh").read_text()
    assert "/usr/local/bin/corvus" in text
    assert "exec sg" in text
    assert WRAPPER.is_file()
    assert SCRIPT.is_file()
    mode = WRAPPER.stat().st_mode
    assert mode & stat.S_IXUSR


def test_help_mentions_brand_and_password_story() -> None:
    result = _run(["bash", str(SCRIPT), "--help"])
    assert result.returncode == 0
    out = result.stdout
    assert "BlackRainLabs.com" in out
    assert "corvus" in out
    assert "chat is not root" in out.lower()
    assert "password" in out.lower()
    assert "isolation" in out.lower()


def test_dry_run_does_not_invoke_apt_get(tmp_path: Path) -> None:
    sentinel = tmp_path / "apt-ran"
    fake = tmp_path / "bin"
    fake.mkdir()
    apt = fake / "apt-get"
    apt.write_text(f"#!/bin/sh\necho ran > {sentinel}\nexit 0\n")
    apt.chmod(0o755)
    sudo = fake / "sudo"
    sudo.write_text('#!/bin/sh\nexec "$@"\n')
    sudo.chmod(0o755)
    env = {
        "PATH": f"{fake}{os.pathsep}{os.environ.get('PATH', '')}",
        "CORVUS_NODE_INSTALL_DRY": "1",
        "CORVUS_NODE_INSTALL_YES": "1",
        "NO_COLOR": "1",
    }
    result = _run(["bash", str(SCRIPT), "--yes"], env=env)
    assert not sentinel.exists()
    combined = result.stdout + result.stderr
    assert "apt-get" not in combined or "dry" in combined
    assert result.returncode in {0, 1}


def test_uid_zero_rejected_in_dry_run() -> None:
    result = _run(
        ["bash", str(SCRIPT), "--yes"],
        env={
            "CORVUS_NODE_INSTALL_DRY": "1",
            "CORVUS_NODE_INSTALL_YES": "1",
            "CORVUS_NODE_INSTALL_FAKE_UID": "0",
            "NO_COLOR": "1",
        },
    )
    assert result.returncode == 1
    assert "not root" in (result.stdout + result.stderr).lower()


def test_dry_run_reports_python_already_current() -> None:
    result = _run(
        ["bash", str(SCRIPT), "--yes"],
        env={
            "CORVUS_NODE_INSTALL_DRY": "1",
            "CORVUS_NODE_INSTALL_YES": "1",
            "NO_COLOR": "1",
        },
    )
    out = result.stdout
    assert "already up to date" in out or "python3" in out


def test_installer_script_stops_a_running_node() -> None:
    text = SCRIPT.read_text()
    assert "Corvus is already running" in text
    assert "Stop Corvus, then continue install?" in text
    assert "systemctl stop corvus-node.service" in text
    assert "source_newer_than_install" in text
    assert "wait_corvus_up" in text
    assert "status --brief" in text
    assert 'echo "${C_BOLD}Status${C_RST}"' in text
