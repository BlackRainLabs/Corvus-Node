"""Guest file tools (tmpdir as /workspace — no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

import pytest

from corvus_node.tools.files import READ_MAX, file_read, file_write, workspace_root
from corvus_node.tools.paths import workspace_relpath


def test_workspace_relpath_allows_under_root() -> None:
    assert workspace_relpath("hello.txt") == "hello.txt"
    assert workspace_relpath("/workspace/a/b") == "a/b"
    assert workspace_relpath("foo/../bar") == "bar"


def test_workspace_relpath_denies_escape() -> None:
    assert workspace_relpath("") is None
    assert workspace_relpath("   ") is None
    assert workspace_relpath("/workspace") is None
    assert workspace_relpath("../etc/passwd") is None
    assert workspace_relpath("/etc/passwd") is None
    assert workspace_relpath("/workspace/../etc/passwd") is None
    assert workspace_relpath("foo/../../etc/passwd") is None


def test_file_read_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_NODE_WORKSPACE", str(tmp_path))
    assert workspace_root() == tmp_path
    (tmp_path / "hello.txt").write_text("from disk", encoding="utf-8")
    assert file_read({"path": "hello.txt"}) == {"path": "hello.txt", "content": "from disk"}
    written = file_write({"path": "out.txt", "content": "guest write"})
    assert written.get("ok") is True
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "guest write"


def test_file_read_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_NODE_WORKSPACE", str(tmp_path))
    result = file_read({"path": "../etc/passwd"})
    assert result["error"] == "path_escape"


def test_file_read_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_NODE_WORKSPACE", str(tmp_path))
    result = file_read({"path": "nope.txt"})
    assert result["error"] == "not found"


def test_file_read_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_NODE_WORKSPACE", str(tmp_path))
    (tmp_path / "big.txt").write_bytes(b"x" * (READ_MAX + 1))
    result = file_read({"path": "big.txt"})
    assert result["error"] == "too large"
