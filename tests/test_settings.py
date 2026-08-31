"""XDG launch.json settings (no VM).

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

import pytest

from corvus_node.node.settings import (
    LaunchSettings,
    SettingsError,
    load_launch,
    merge_launch,
    save_launch,
)
from corvus_node.node.workspace import WorkspaceError


def test_missing_file_is_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    loaded = load_launch()
    assert loaded.tools == frozenset()
    assert loaded.workspace is None


def test_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    save_launch(LaunchSettings(tools=frozenset({"echo"}), workspace=str(ws)))
    loaded = load_launch()
    assert loaded.tools == frozenset({"echo"})
    assert loaded.workspace == str(ws.resolve())


def test_invalid_json_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "corvus-node" / "launch.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError, match="invalid"):
        load_launch()


def test_merge_flags_override_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    stored = LaunchSettings(tools=frozenset({"echo"}), workspace=str(ws))
    other = tmp_path / "other"
    other.mkdir()
    merged = merge_launch(stored, tools="file_read", workspace=(str(other),))
    assert merged.tools == frozenset({"file_read"})
    assert merged.workspace == str(other.resolve())


def test_merge_two_workspaces_fails(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    with pytest.raises(WorkspaceError, match="one --workspace path"):
        merge_launch(LaunchSettings(), workspace=(str(a), str(b)))
