"""Host workspace I/O. Node reads and writes the allowlisted directory.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from corvus_node.tools.files import READ_MAX, WRITE_MAX
from corvus_node.tools.paths import workspace_relpath


class WorkspaceError(ValueError):
    """Workspace path is missing, not a directory, or not usable."""


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
