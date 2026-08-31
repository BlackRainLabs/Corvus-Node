"""Host workspace I/O (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

import pytest

from corvus_node.node.workspace import (
    WorkspaceError,
    host_file_read,
    host_file_write,
    resolve_host_workspace,
)


def test_resolve_host_workspace(tmp_path: Path) -> None:
    assert resolve_host_workspace(tmp_path) == tmp_path.resolve()
    with pytest.raises(WorkspaceError, match="missing"):
        resolve_host_workspace(tmp_path / "nope")
    file_path = tmp_path / "file"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="not a directory"):
        resolve_host_workspace(file_path)


def test_host_file_read_write(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("old", encoding="utf-8")
    assert host_file_read(tmp_path, "notes.txt")["content"] == "old"
    written = host_file_write(tmp_path, "notes.txt", "reviewed")
    assert written.get("ok") is True
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "reviewed"


def test_host_file_read_sees_user_edit(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("first", encoding="utf-8")
    assert host_file_read(tmp_path, "notes.txt")["content"] == "first"
    notes.write_text("user edited", encoding="utf-8")
    assert host_file_read(tmp_path, "notes.txt")["content"] == "user edited"


def test_host_file_refuses_escape(tmp_path: Path) -> None:
    assert host_file_read(tmp_path, "../etc/passwd")["error"] == "path_escape"
    assert host_file_write(tmp_path, "/etc/passwd", "x")["error"] == "path_escape"


def test_host_file_refuses_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    assert host_file_read(tmp_path, "link.txt")["error"] == "path_escape"
    assert host_file_write(tmp_path, "link.txt", "x")["error"] == "path_escape"
    assert outside.read_text(encoding="utf-8") == "nope"


def test_host_file_write_nested(tmp_path: Path) -> None:
    result = host_file_write(tmp_path, "sub/a.txt", "hi")
    assert result.get("ok") is True
    assert (tmp_path / "sub" / "a.txt").read_text(encoding="utf-8") == "hi"
