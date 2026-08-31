"""XDG launch rules. Applied at start; a running VM is not hot-patched.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from corvus_node.node.workspace import WorkspaceError, resolve_host_workspace

LAUNCH_NAME = "launch.json"


class SettingsError(ValueError):
    """launch.json is missing fields, invalid, or a path is unusable."""


@dataclass(frozen=True)
class LaunchSettings:
    tools: frozenset[str] = frozenset()
    workspace: str | None = None


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg) / "corvus-node"
    return Path.home() / ".config" / "corvus-node"


def launch_path() -> Path:
    return config_dir() / LAUNCH_NAME


def parse_tools(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def load_launch() -> LaunchSettings:
    path = launch_path()
    if not path.is_file():
        return LaunchSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsError(f"invalid launch file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"invalid launch file {path}: expected object")
    tools_raw = data.get("tools", [])
    if tools_raw is None:
        tools_raw = []
    if not isinstance(tools_raw, list) or not all(isinstance(t, str) for t in tools_raw):
        raise SettingsError(f"invalid launch file {path}: tools must be a list of strings")
    tools = frozenset(t.strip() for t in tools_raw if t.strip())
    workspace = data.get("workspace")
    if workspace is not None:
        if not isinstance(workspace, str) or not workspace.strip():
            raise SettingsError(f"invalid launch file {path}: workspace must be a string")
        workspace = str(resolve_host_workspace(workspace.strip()))
    return LaunchSettings(tools=tools, workspace=workspace)


def save_launch(settings: LaunchSettings) -> Path:
    path = launch_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "tools": sorted(settings.tools),
        "workspace": settings.workspace,
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def merge_launch(
    stored: LaunchSettings,
    *,
    tools: str | None = None,
    workspace: tuple[str, ...] | None = None,
) -> LaunchSettings:
    """CLI flags override the file. None means leave that field to the file."""
    out_tools = stored.tools if tools is None else parse_tools(tools)
    if workspace is None:
        out_ws = stored.workspace
    elif len(workspace) > 1:
        raise WorkspaceError("v0.1.5 accepts one --workspace path")
    elif len(workspace) == 0:
        out_ws = None
    else:
        out_ws = str(resolve_host_workspace(workspace[0]))
    return LaunchSettings(tools=out_tools, workspace=out_ws)


def format_settings(settings: LaunchSettings) -> str:
    tools = ",".join(sorted(settings.tools)) or "(none)"
    workspace = settings.workspace or "(none)"
    return f"tools: {tools}\nworkspace: {workspace}\n"
