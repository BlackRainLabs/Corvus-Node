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


def test_install_wrapper_is_executable() -> None:
    assert WRAPPER.is_file()
    assert SCRIPT.is_file()
    mode = WRAPPER.stat().st_mode
    assert mode & stat.S_IXUSR


def test_help_mentions_brand_jailer_and_newgrp() -> None:
    result = _run(["bash", str(SCRIPT), "--help"])
    assert result.returncode == 0
    out = result.stdout
    assert "BlackRainLabs.com" in out
    assert "jailer" in out.lower()
    assert "corvus" in out
    assert "chat is not root" in out.lower() or "not sudo to chat" in out.lower()
    assert "newgrp" in out.lower()


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
