"""Per-version operator CLI copy. Update when the version's runnable surface changes.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from corvus_node import __version__

THIS_BUILD = "stub chat, vm start/stop/status, echo, file_read/write"
NOT_IN_THIS_BUILD = "provider LLM, skills, durable Engine 4, GUI"
LLM_NAME = "stub"
CLI_NAME = "corvus"

HELP_BLURB = (
    f"Corvus-Node {__version__} — one agent in a Firecracker VM ({LLM_NAME} LLM).\n"
    "Install once (sudo make install), then no sudo:\n"
    "  corvus vm start   →   corvus chat   →   /exit   →   corvus stop\n"
    "CLI talks only to Node. Node owns jailer, vsock, and RBAC. No TCP product mode."
)

HELP_EPILOG = (
    f"This build: {THIS_BUILD}.\n"
    f"Not in this build: {NOT_IN_THIS_BUILD}.\n"
    "sudo make install once (group + systemd Node). After that, vm/chat/run "
    "do not use sudo. vm start|stop|status is the Firecracker guest; the Node "
    "service stays up. start/stop are aliases for vm start/stop; stop always "
    "shuts down the guest VM first (Node stays up). "
    "chat is a live session until /exit. "
    "corvus update refreshes the installed app from GitHub when a newer tag exists; "
    "it will not overwrite a local unreleased tree."
)


def build_lines() -> list[str]:
    return [
        f"Corvus-Node {__version__}",
        f"LLM: {LLM_NAME}",
        f"This build: {THIS_BUILD}.",
        f"Not in this build: {NOT_IN_THIS_BUILD}.",
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
