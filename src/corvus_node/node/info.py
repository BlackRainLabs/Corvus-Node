"""Per-version operator CLI copy. Update when the version's runnable surface changes.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from corvus_node import __version__

THIS_BUILD = "chat, start/stop, echo, file read/write/list, default workspace, splash GUI"
NOT_IN_THIS_BUILD = "live AI model, extra skills, saved memory, full operator window"
LLM_NAME = "stub"
CLI_NAME = "corvus"

HELP_BLURB = (
    f"Corvus-Node {__version__} — a private AI agent on your Linux PC ({LLM_NAME} model).\n"
    "Install once (./install.sh), then:\n"
    "  corvus start        bring Corvus-Node up (asks before the VM; Enter skips)\n"
    "  corvus vm start   →   corvus chat   →   /exit   →   corvus vm stop\n"
    "  corvus settings     show the folder and tools (the default folder stays off)\n"
    "  corvus settings set workspace default\n"
    "  corvus gui          splash (this preview; does not talk to the agent)\n"
    "  corvus stop         shut everything down (asks first)\n"
    "The agent stays isolated. You do not sudo to chat."
)

HELP_EPILOG = (
    f"This preview: {THIS_BUILD}.\n"
    f"Not yet: {NOT_IN_THIS_BUILD}.\n"
    "corvus start brings Corvus-Node up and asks before starting the isolated agent "
    "(Enter skips the VM). vm start / chat / vm stop talk to the agent. "
    "Corvus-Node stays ready in the background after vm stop. corvus stop shuts the "
    "agent and Corvus-Node down (asks first). chat lasts until /exit. "
    "corvus gui shows the splash if PySide/Qt is installed. "
    "corvus settings set workspace default allows the default folder; "
    "settings set workspace /path allows another folder; "
    "settings unset workspace turns it off and leaves the files. "
    "settings set tools echo,file_read,file_write,file_list remembers tools. "
    "Allowing a folder does not turn tools on. A running session keeps the old rules "
    "until vm stop then vm start. "
    "corvus update installs a newer GitHub release (CLI and GUI; "
    "stops Corvus-Node first if it is running; asks before replacing)."
)


def build_lines() -> list[str]:
    return [
        f"Corvus-Node {__version__}",
        f"LLM: {LLM_NAME}",
        f"This preview: {THIS_BUILD}.",
        f"Not yet: {NOT_IN_THIS_BUILD}.",
    ]


def format_workspace_line(workspace: str | None, *, default_workspace: str) -> str:
    if workspace:
        return f"Workspace: {workspace} (allowed)"
    return f"Workspace: {default_workspace} (disabled)"


def format_runtime_status(
    pid: int | None,
    snap: dict | None,
    *,
    error: str = "",
    default_workspace: str = "",
) -> list[str]:
    """Node service vs guest VM. Node down is not the same as VM idle."""
    if pid is None:
        return ["Node: down", "VM: (none)"]
    if snap is None:
        extra = f" ({error})" if error else ""
        return [f"Node: up  pid={pid}{extra}", "VM: (unknown)"]
    lines = [f"Node: up  pid={snap.get('pid', pid)}"]
    lines.extend(format_vm_status(snap, default_workspace=default_workspace))
    return lines


def format_vm_status(snap: dict, *, default_workspace: str = "") -> list[str]:
    state = str(snap.get("state") or "idle")
    vm_id = str(snap.get("vm_instance_id") or "")
    if state == "running":
        lines = [f"VM: running  id={vm_id or '(none)'}"]
        tools = ",".join(snap.get("tools") or []) or "(none)"
        workspace = snap.get("workspace") or []
        lines.append(f"Tools: {tools}")
        if workspace:
            lines.append(f"Workspace: {workspace[0]} (allowed)")
        elif default_workspace:
            lines.append(f"Workspace: {default_workspace} (disabled)")
        else:
            lines.append("Workspace: (disabled)")
        return lines
    return [f"VM: {state}"]
