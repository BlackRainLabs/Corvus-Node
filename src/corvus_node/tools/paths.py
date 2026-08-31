"""Workspace path checks. Guest and Node share this module.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import posixpath

WORKSPACE_GUEST_ROOT = "/workspace"


def workspace_relpath(raw: str, *, root: str = WORKSPACE_GUEST_ROOT) -> str | None:
    """Return a relative path under root, or None on escape / empty / root itself."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    joined = text if text.startswith("/") else posixpath.join(root, text)
    normalized = posixpath.normpath(joined)
    root_n = posixpath.normpath(root)
    if normalized == root_n:
        return None
    prefix = root_n.rstrip("/") + "/"
    if not normalized.startswith(prefix):
        return None
    rel = normalized[len(prefix) :]
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        return None
    return rel
