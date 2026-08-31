"""Guest image payload: protocol, runtime, tools. Not the host TCB.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

GUEST_PACKAGES = ("protocol", "runtime", "tools")
FORBIDDEN_GUEST_NAMES = frozenset(
    {
        "node",
        "vm",
        "policy",
        "llm",
        "audit",
        "gateway",
        "identity",
        "memory",
        "cli.py",
    }
)
GUEST_UID = 1000
GUEST_GID = 1000
GUEST_USER = "corvus"


def install_into(tree: Path, repo_root: Path) -> None:
    """Copy the slim guest package and entry scripts into a rootfs tree."""
    src = repo_root / "src" / "corvus_node"
    dest = tree / "opt" / "corvus" / "src" / "corvus_node"
    guest_dir = tree / "opt" / "corvus" / "guest"
    dest.parent.mkdir(parents=True, exist_ok=True)
    guest_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(src / "__init__.py", dest / "__init__.py")
    for name in GUEST_PACKAGES:
        shutil.copytree(src / name, dest / name, dirs_exist_ok=True)
    shutil.copy2(repo_root / "guest" / "run_guest.py", guest_dir / "run_guest.py")
    shutil.copy2(repo_root / "guest" / "init.sh", guest_dir / "init.sh")
    (guest_dir / "init.sh").chmod(0o755)
    workspace = tree / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(workspace, GUEST_UID, GUEST_GID)
    except OSError:
        pass
    _write_guest_user(tree)
    _strip_pycache(tree / "opt" / "corvus")
    assert_slim(tree)


def _write_guest_user(tree: Path) -> None:
    etc = tree / "etc"
    etc.mkdir(parents=True, exist_ok=True)
    passwd = etc / "passwd"
    group = etc / "group"
    passwd_text = passwd.read_text(encoding="utf-8") if passwd.exists() else ""
    group_text = group.read_text(encoding="utf-8") if group.exists() else ""
    if f"{GUEST_USER}:" not in passwd_text:
        with passwd.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{GUEST_USER}:x:{GUEST_UID}:{GUEST_GID}::/nonexistent:/usr/sbin/nologin\n"
            )
    if f"{GUEST_USER}:" not in group_text:
        with group.open("a", encoding="utf-8") as handle:
            handle.write(f"{GUEST_USER}:x:{GUEST_GID}:\n")


def _strip_pycache(root: Path) -> None:
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def assert_slim(tree: Path) -> None:
    base = tree / "opt" / "corvus" / "src" / "corvus_node"
    for name in FORBIDDEN_GUEST_NAMES:
        if (base / name).exists():
            raise RuntimeError(f"host TCB {name!r} must not be in the guest payload")
