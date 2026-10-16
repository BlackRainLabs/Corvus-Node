"""Host workspace I/O (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

import pytest

from corvus_node.node.workspace import (
    LIST_MAX,
    WorkspaceError,
    default_workspace_path,
    ensure_default_workspace,
    host_file_list,
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


def test_default_workspace_is_created_without_launch_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    created = ensure_default_workspace()
    assert created == (tmp_path / "data" / "corvus-node" / "workspace").resolve()
    assert created.is_dir()
    assert (created.stat().st_mode & 0o777) == 0o700
    assert not (tmp_path / "config" / "corvus-node" / "launch.json").exists()
    assert default_workspace_path() == tmp_path / "data" / "corvus-node" / "workspace"


def test_host_file_list_one_level(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("no", encoding="utf-8")
    listed = host_file_list(tmp_path, "/workspace")
    names = {entry["name"]: entry["kind"] for entry in listed["entries"]}
    assert names == {"notes.txt": "file", "sub": "dir"}
    assert "nested.txt" not in names
    assert host_file_list(tmp_path, ".")["entries"] == listed["entries"]
    assert host_file_list(tmp_path, "")["path"] == "/workspace"


def test_host_file_list_subdir_and_errors(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    listed = host_file_list(tmp_path, "sub")
    assert listed["entries"] == [{"name": "a.txt", "kind": "file"}]
    assert host_file_list(tmp_path, "notes.txt")["error"] == "not a directory"
    assert host_file_list(tmp_path, "missing")["error"] == "not found"
    assert host_file_list(tmp_path, "../etc")["error"] == "path_escape"


def test_host_file_list_skips_symlink_target(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    listed = host_file_list(tmp_path, "/workspace")
    assert listed["entries"] == [{"name": "link.txt", "kind": "symlink"}]
    assert "nope" not in str(listed)
    linked = tmp_path / "out"
    linked.symlink_to(tmp_path.parent)
    assert host_file_list(tmp_path, "out")["error"] == "path_escape"


def test_host_file_list_caps_entries(tmp_path: Path) -> None:
    for index in range(LIST_MAX + 1):
        (tmp_path / f"f{index:04d}.txt").write_text("x", encoding="utf-8")
    listed = host_file_list(tmp_path, ".")
    assert len(listed["entries"]) == LIST_MAX
    assert listed.get("truncated") is True
