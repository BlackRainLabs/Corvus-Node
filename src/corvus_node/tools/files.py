"""Guest file tools. Paths must stay under /workspace.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from corvus_node.tools.paths import workspace_relpath

READ_MAX = 65_536
WRITE_MAX = 65_536


class PathEscape(ValueError):
    """Requested path is outside the workspace root."""


def workspace_root() -> Path:
    raw = os.environ.get("CORVUS_NODE_WORKSPACE", "/workspace")
    return Path(raw)


def resolve_under_workspace(raw: str, *, root: Path | None = None) -> Path:
    rel = workspace_relpath(raw)
    if rel is None:
        raise PathEscape(raw)
    base = (root or workspace_root()).resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise PathEscape(raw) from exc
    return target


def file_read(arguments: dict[str, Any]) -> dict[str, Any]:
    path = str(arguments.get("path", ""))
    try:
        target = resolve_under_workspace(path)
    except PathEscape:
        return {"error": "path_escape", "path": path}
    if not target.is_file():
        return {"error": "not found", "path": path}
    size = target.stat().st_size
    if size > READ_MAX:
        return {"error": "too large", "path": path, "size": size}
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


def file_write(arguments: dict[str, Any]) -> dict[str, Any]:
    path = str(arguments.get("path", ""))
    content = str(arguments.get("content", ""))
    if len(content) > WRITE_MAX:
        return {"error": "too large", "path": path, "size": len(content)}
    try:
        target = resolve_under_workspace(path)
    except PathEscape:
        return {"error": "path_escape", "path": path}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "ok": True, "bytes": len(content.encode("utf-8"))}
