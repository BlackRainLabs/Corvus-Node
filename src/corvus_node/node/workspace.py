"""Host workspace I/O. Node reads and writes the allowlisted directory.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from corvus_node.tools.files import READ_MAX, WRITE_MAX
from corvus_node.tools.paths import workspace_list_relpath, workspace_relpath

LIST_MAX = 256


class WorkspaceError(ValueError):
    """Workspace path is missing, not a directory, or not usable."""


def data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / "corvus-node"
    return Path.home() / ".local" / "share" / "corvus-node"


def default_workspace_path() -> Path:
    """Operator-owned default tree. Not on the allowlist until settings allow it."""
    return data_dir() / "workspace"


def ensure_default_workspace() -> Path:
    """Create the default workspace (0700) if missing. Does not write launch rules."""
    path = default_workspace_path()
    if path.is_symlink():
        raise WorkspaceError(f"workspace is a symlink: {path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceError(f"workspace unreadable: {path}") from exc
    if path.is_symlink() or not path.is_dir():
        raise WorkspaceError(f"workspace is not a directory: {path}")
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise WorkspaceError(f"workspace unreadable: {path}") from exc
    return path.resolve()


def resolve_host_workspace(path: str | Path) -> Path:
    raw = Path(path).expanduser()
    try:
        resolved = raw.resolve()
    except OSError as exc:
        raise WorkspaceError(f"workspace unreadable: {path}") from exc
    if not resolved.exists():
        raise WorkspaceError(f"workspace missing: {path}")
    if not resolved.is_dir():
        raise WorkspaceError(f"workspace is not a directory: {path}")
    if not os.access(resolved, os.R_OK | os.X_OK):
        raise WorkspaceError(f"workspace unreadable: {path}")
    return resolved


def _target(root: Path, raw_path: str) -> Path | None:
    rel = workspace_relpath(raw_path)
    if rel is None:
        return None
    candidate = root / rel
    if candidate.is_symlink():
        return None
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return candidate


def host_file_read(root: Path, raw_path: str) -> dict[str, Any]:
    target = _target(root, raw_path)
    if target is None:
        return {"error": "path_escape", "path": raw_path}
    if target.is_symlink() or not target.is_file():
        return {"error": "not found", "path": raw_path}
    try:
        size = target.stat().st_size
        if size > READ_MAX:
            return {"error": "too large", "path": raw_path, "size": size}
        return {"path": raw_path, "content": target.read_text(encoding="utf-8", errors="replace")}
    except OSError as exc:
        return {"error": str(exc), "path": raw_path}


def host_file_write(root: Path, raw_path: str, content: str) -> dict[str, Any]:
    if len(content) > WRITE_MAX:
        return {"error": "too large", "path": raw_path, "size": len(content)}
    target = _target(root, raw_path)
    if target is None:
        return {"error": "path_escape", "path": raw_path}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            return {"error": "path_escape", "path": raw_path}
        if target.exists() and not target.is_file():
            return {"error": "not a file", "path": raw_path}
        target.write_text(content, encoding="utf-8")
        owner = root.stat()
        try:
            os.chown(target, owner.st_uid, owner.st_gid)
        except OSError:
            pass
    except OSError as exc:
        return {"error": str(exc), "path": raw_path}
    return {"path": raw_path, "ok": True, "bytes": len(content.encode("utf-8"))}


def host_file_list(root: Path, raw_path: str) -> dict[str, Any]:
    """One directory level under the allowlisted root. Symlinks are not followed."""
    rel = workspace_list_relpath(raw_path)
    if rel is None:
        return {"error": "path_escape", "path": raw_path}
    if rel == "":
        target = root
        display = "/workspace"
    else:
        target = _target(root, raw_path)
        if target is None:
            return {"error": "path_escape", "path": raw_path}
        display = raw_path
    if target.is_symlink():
        return {"error": "path_escape", "path": raw_path}
    if not target.exists():
        return {"error": "not found", "path": raw_path}
    if not target.is_dir():
        return {"error": "not a directory", "path": raw_path}
    try:
        children = sorted(target.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        return {"error": str(exc), "path": raw_path}
    truncated = len(children) > LIST_MAX
    entries: list[dict[str, str]] = []
    for child in children[:LIST_MAX]:
        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "dir"
        elif child.is_file():
            kind = "file"
        else:
            kind = "other"
        entries.append({"name": child.name, "kind": kind})
    result: dict[str, Any] = {"path": display, "entries": entries}
    if truncated:
        result["truncated"] = True
    return result
