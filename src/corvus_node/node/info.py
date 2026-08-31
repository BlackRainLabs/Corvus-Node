"""Per-version operator CLI copy. Update when the version's runnable surface changes.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from corvus_node import __version__

THIS_BUILD = "chat, start/stop, echo, file read/write, splash GUI"
NOT_IN_THIS_BUILD = "live AI model, extra skills, saved memory, full operator window"
LLM_NAME = "stub"
CLI_NAME = "corvus"

HELP_BLURB = (
    f"Corvus-Node {__version__} — a private AI agent on your Linux PC ({LLM_NAME} model).\n"
    "Install once (./install.sh), then:\n"
    "  corvus start        bring Corvus-Node up (asks before the VM; Enter skips)\n"
    "  corvus vm start   →   corvus chat   →   /exit   →   corvus vm stop\n"
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


def format_runtime_status(pid: int | None, snap: dict | None, *, error: str = "") -> list[str]:
    """Node service vs guest VM. Node down is not the same as VM idle."""
    if pid is None:
        return ["Node: down", "VM: (none)"]
    if snap is None:
        extra = f" ({error})" if error else ""
        return [f"Node: up  pid={pid}{extra}", "VM: (unknown)"]
    lines = [f"Node: up  pid={snap.get('pid', pid)}"]
    lines.extend(format_vm_status(snap))
    return lines


def format_vm_status(snap: dict) -> list[str]:
    state = str(snap.get("state") or "idle")
    vm_id = str(snap.get("vm_instance_id") or "")
    if state == "running":
        lines = [f"VM: running  id={vm_id or '(none)'}"]
        tools = ",".join(snap.get("tools") or []) or "(none)"
        workspace = snap.get("workspace") or []
        lines.append(f"Tools: {tools}")
        lines.append(f"Workspace: {workspace[0] if workspace else '(none)'}")
        return lines
    return [f"VM: {state}"]
