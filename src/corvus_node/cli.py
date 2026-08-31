"""Host CLI: operator surface (same layer as the GUI). Talks only to Node.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys

from corvus_node import __version__
from corvus_node.gateway.adapter import LocalCliAdapter
from corvus_node.node.chatview import chrome_from_snapshot, run_live_chat
from corvus_node.node.control import (
    INSTALL_HINT,
    ControlClient,
    ControlError,
    node_pid,
    product_prefix,
    runtime_dir,
)
from corvus_node.node.daemon import (
    AlreadyRunning,
    rpc_shutdown,
    rpc_start,
    rpc_status,
    rpc_stop,
    serve_forever,
    start_daemon,
    wait_node_gone,
    wait_node_ready,
)
from corvus_node.node.info import (
    CLI_NAME,
    HELP_BLURB,
    HELP_EPILOG,
    build_lines,
    format_runtime_status,
    format_vm_status,
)
from corvus_node.node.session import LaunchConfig
from corvus_node.node.settings import (
    LaunchSettings,
    SettingsError,
    format_settings,
    load_launch,
    merge_launch,
    parse_tools,
    save_launch,
)
from corvus_node.node.update import check_version, format_version_status, github_install_ref
from corvus_node.node.workspace import WorkspaceError, resolve_host_workspace
from corvus_node.vm.launcher import (
    GuestBootTimeout,
    IsolationUnavailable,
    ensure_runtime,
    launch_turn,
    probe_isolation,
    require_root,
)

SYSTEMD_UNIT = "corvus-node.service"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=CLI_NAME,
        description=HELP_BLURB,
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("help", help="show this help")
    sub.add_parser("version", help="print version")
    status_p = sub.add_parser("status", help="is Corvus-Node up? is an agent session running?")
    status_p.add_argument(
        "--brief",
        action="store_true",
        help="Node and VM only (no preview, version, or isolation)",
    )
    start_p = sub.add_parser(
        "start",
        help="start Corvus-Node; asks before starting the isolated agent (Enter = no)",
    )
    _launch_flags(start_p)
    _yes_flag(start_p, help_text="also start the isolated agent (do not ask)")
    sub.add_parser("chat", help="talk to the agent until /exit")
    stop_p = sub.add_parser("stop", help="end the session and shut Corvus-Node down")
    _yes_flag(stop_p)
    vm_p = sub.add_parser("vm", help="the isolated agent session")
    vm_sub = vm_p.add_subparsers(dest="vm_cmd", required=False)
    vm_start = vm_sub.add_parser("start", help="start the isolated agent")
    _launch_flags(vm_start)
    vm_stop = vm_sub.add_parser("stop", help="end the agent session; Corvus-Node stays ready")
    _yes_flag(vm_stop)
    vm_sub.add_parser("status", help="agent session only")
    update_p = sub.add_parser("update", help="install a newer Corvus-Node release")
    _yes_flag(update_p)
    settings_p = sub.add_parser("settings", help="remember tools and folder for next start")
    settings_sub = settings_p.add_subparsers(dest="settings_cmd")
    set_p = settings_sub.add_parser("set", help="set a launch rule")
    set_p.add_argument("key", choices=["tools", "workspace"])
    set_p.add_argument("value")
    unset_p = settings_sub.add_parser("unset", help="clear a launch rule")
    unset_p.add_argument("key", choices=["tools", "workspace"])
    run_p = sub.add_parser("run", help="one reply, then done")
    run_p.add_argument(
        "--once",
        action="store_true",
        help="one user message, then exit",
    )
    run_p.add_argument("text", nargs="?", help="user turn text")
    _launch_flags(run_p)
    serve_p = sub.add_parser("serve", help=argparse.SUPPRESS)
    _launch_flags(serve_p)
    args = parser.parse_args(argv)
    if args.command in {None, "help"}:
        parser.print_help()
        return 0
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "status":
        return _status(brief=bool(args.brief))
    if args.command == "settings":
        return _settings(args)
    if args.command == "chat":
        return _run_chat()
    if args.command == "stop":
        return _product_stop(yes=bool(getattr(args, "yes", False)))
    if args.command == "vm":
        return _vm(args)
    if args.command == "update":
        return _update(yes=bool(getattr(args, "yes", False)))
    try:
        merged = _merged_launch(args)
    except (WorkspaceError, SettingsError) as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    if args.command == "start":
        return _product_start(merged, yes=bool(getattr(args, "yes", False)))
    if args.command == "serve":
        return _serve(merged)
    if args.command == "run":
        if not args.once or not args.text:
            print(f"corvus: v{__version__} requires: run --once TEXT", file=sys.stderr)
            return 2
        return _run_once(args.text, merged)
    print(f"corvus: unknown command {args.command}", file=sys.stderr)
    return 2


def _yes_flag(
    parser: argparse.ArgumentParser,
    *,
    help_text: str = "skip the confirmation prompt",
) -> None:
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help=help_text,
    )


def _launch_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tools",
        default=None,
        help="comma-separated tools to allow (echo, file_read, file_write)",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        default=None,
        help="folder the agent may read/write (one path)",
    )


def _merged_launch(args: argparse.Namespace) -> LaunchSettings:
    stored = load_launch()
    workspace = tuple(args.workspace) if args.workspace is not None else None
    return merge_launch(stored, tools=args.tools, workspace=workspace)


def _config(merged: LaunchSettings, *, once: bool = False, user_text: str = "") -> LaunchConfig:
    adapter = LocalCliAdapter(user_text)
    paths = (merged.workspace,) if merged.workspace else ()
    return LaunchConfig(
        user_text=user_text,
        allowed_tools=merged.tools,
        workspace_paths=paths,
        principal=adapter.principal(),
        once=once,
    )


def _launch_errors(exc: BaseException) -> int:
    if isinstance(exc, AlreadyRunning):
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    if isinstance(exc, IsolationUnavailable):
        print(f"corvus: isolation unavailable: {exc}", file=sys.stderr)
        print(
            "Refusing to run without isolation (virtualization is required).",
            file=sys.stderr,
        )
        return 2
    if isinstance(exc, GuestBootTimeout):
        print(f"corvus: guest boot timed out: {exc}", file=sys.stderr)
        return 2
    if isinstance(exc, OSError):
        print(f"corvus: failed to launch microVM: {exc}", file=sys.stderr)
        return 2
    raise exc


def _status(*, brief: bool = False) -> int:
    pid = node_pid()
    snap: dict | None = None
    error = ""
    if pid is not None:
        try:
            snap = rpc_status()
        except ControlError as exc:
            error = str(exc)
    for line in format_runtime_status(pid, snap, error=error):
        print(line)
    if pid is None:
        print(f"Hint: {INSTALL_HINT}")
    if brief:
        return 0
    print()
    for line in build_lines():
        print(line)
    print()
    sys.stdout.write(format_version_status(check_version()))
    print()
    gaps = probe_isolation()
    if gaps:
        print("Isolation: not ready")
        for gap in gaps:
            print(f"  - {gap}")
    else:
        print("Isolation: ready")
    return 0


def _vm(args: argparse.Namespace) -> int:
    cmd = getattr(args, "vm_cmd", None)
    if cmd == "status":
        return _vm_status()
    if cmd == "stop":
        return _vm_stop(yes=bool(getattr(args, "yes", False)))
    if cmd == "start":
        try:
            merged = _merged_launch(args)
        except (WorkspaceError, SettingsError) as exc:
            print(f"corvus: {exc}", file=sys.stderr)
            return 2
        return _start(merged)
    print(f"corvus: v{__version__} requires: vm start|stop|status", file=sys.stderr)
    return 2


def _vm_status() -> int:
    pid = node_pid()
    if pid is None:
        print("VM: (none)")
        print(f"corvus: {INSTALL_HINT}", file=sys.stderr)
        return 2
    try:
        snap = rpc_status()
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    for line in format_vm_status(snap):
        print(line)
    return 0


def _settings(args: argparse.Namespace) -> int:
    cmd = getattr(args, "settings_cmd", None)
    try:
        stored = load_launch()
        if cmd is None:
            sys.stdout.write(format_settings(stored))
            if node_pid() is not None:
                try:
                    snap = rpc_status()
                    tools = ",".join(snap.get("tools") or []) or "(none)"
                    ws = snap.get("workspace") or []
                    print("active launch (unchanged until vm stop then vm start):")
                    print(f"tools: {tools}")
                    print(f"workspace: {ws[0] if ws else '(none)'}")
                except ControlError:
                    pass
            return 0
        if cmd == "set":
            if args.key == "tools":
                stored = LaunchSettings(tools=parse_tools(args.value), workspace=stored.workspace)
            else:
                stored = LaunchSettings(
                    tools=stored.tools,
                    workspace=str(resolve_host_workspace(args.value)),
                )
            save_launch(stored)
        elif cmd == "unset":
            if args.key == "tools":
                stored = LaunchSettings(tools=frozenset(), workspace=stored.workspace)
            else:
                stored = LaunchSettings(tools=stored.tools, workspace=None)
            save_launch(stored)
        else:
            print(f"corvus: unknown settings command {cmd}", file=sys.stderr)
            return 2
    except (WorkspaceError, SettingsError) as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(format_settings(load_launch()))
    if node_pid() is not None:
        print(
            "corvus: running VM is unchanged until vm stop then vm start",
            file=sys.stderr,
        )
    return 0


def _start(merged: LaunchSettings) -> int:
    config = _config(merged)
    try:
        rpc_start(config)
    except ControlError as exc:
        if (
            exc.code == "not_running"
            and os.geteuid() == 0
            and os.environ.get("CORVUS_NODE_SMOKE", "").strip() == "1"
        ):
            try:
                start_daemon(config)
            except (IsolationUnavailable, GuestBootTimeout, AlreadyRunning, OSError) as boot:
                return _launch_errors(boot)
        else:
            print(f"corvus: {exc}", file=sys.stderr)
            if exc.code == "not_running":
                print(f"corvus: {INSTALL_HINT}", file=sys.stderr)
            return 2
    print("corvus: agent started", file=sys.stderr)
    return 0


def _runtime_is_product_install() -> bool:
    return runtime_dir().resolve() == (product_prefix() / "run").resolve()


def _ensure_node_up() -> int:
    """Bring the Node service up. Does not start the guest VM."""
    if node_pid() is not None:
        return 0
    if not _runtime_is_product_install():
        print(f"corvus: {INSTALL_HINT}", file=sys.stderr)
        return 2
    start_rc = _start_systemd_unit()
    if start_rc != 0:
        print(f"corvus: Corvus-Node did not start ({INSTALL_HINT})", file=sys.stderr)
        return 2
    if not wait_node_ready():
        print(f"corvus: Corvus-Node did not become ready ({INSTALL_HINT})", file=sys.stderr)
        return 2
    print("corvus: Corvus-Node started", file=sys.stderr)
    return 0


def _product_start(merged: LaunchSettings, *, yes: bool) -> int:
    node_rc = _ensure_node_up()
    if node_rc != 0:
        return node_rc
    pid = node_pid()
    if _vm_is_running(pid):
        print("corvus: agent already running", file=sys.stderr)
        return 0
    if not _confirm(
        "Start the isolated agent (VM) as well?",
        yes=yes,
        missing_tty="corvus: not starting the VM (pass --yes to start it)",
    ):
        print("corvus: Corvus-Node is ready; agent not running (corvus vm start)", file=sys.stderr)
        return 0
    return _start(merged)


def _serve(merged: LaunchSettings) -> int:
    try:
        require_root()
        ensure_runtime()
        asyncio.run(serve_forever(_config(merged)))
    except (IsolationUnavailable, GuestBootTimeout, OSError) as exc:
        return _launch_errors(exc)
    return 0


def _run_once(text: str, merged: LaunchSettings) -> int:
    if node_pid() is not None:
        return _run_once_via_node(text, merged)
    smoke = os.environ.get("CORVUS_NODE_SMOKE", "").strip() == "1"
    if os.geteuid() != 0 or not smoke:
        print(f"corvus: {INSTALL_HINT}", file=sys.stderr)
        return 2
    config = _config(merged, once=True, user_text=text)
    try:
        response = asyncio.run(launch_turn(config))
    except (IsolationUnavailable, GuestBootTimeout, OSError) as exc:
        return _launch_errors(exc)
    print(response)
    return 0


def _run_once_via_node(text: str, merged: LaunchSettings) -> int:
    config = _config(merged)
    client: ControlClient | None = None
    try:
        snap = rpc_status()
        if snap.get("state") != "running":
            rpc_start(config)
        client = ControlClient()
        client.connect()
        client.send("chat_attach")
        frame = client.read()
        if frame["type"] != "waiting":
            print(f"corvus: unexpected attach reply {frame['type']}", file=sys.stderr)
            return 2
        client.send("user", {"text": text})
        reply = client.read()
        if reply["type"] != "agent":
            print(f"corvus: unexpected chat reply {reply['type']}", file=sys.stderr)
            return 2
        print(str(reply["payload"].get("text", "")), flush=True)
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()
        try:
            rpc_stop()
        except ControlError:
            pass
    return 0


def _run_chat() -> int:
    try:
        snap = rpc_status()
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    if snap.get("state") != "running":
        print("corvus: the agent is not running; corvus vm start", file=sys.stderr)
        return 2
    chrome = chrome_from_snapshot(snap)
    client = ControlClient()
    try:
        client.connect()
        client.send("chat_attach")
        frame = client.read()
        if frame["type"] != "waiting":
            print(f"corvus: unexpected attach reply {frame['type']}", file=sys.stderr)
            return 2
        return run_live_chat(client, chrome)
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    finally:
        client.close()


def _vm_is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        return rpc_status().get("state") == "running"
    except ControlError:
        return False


def _confirm(prompt: str, *, yes: bool, missing_tty: str | None = None) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            missing_tty or "corvus: not a TTY; pass --yes to confirm",
            file=sys.stderr,
        )
        return False
    print(f"{prompt} [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = sys.stdin.readline()
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def _print_vm_stop_explain(*, running: bool) -> None:
    print("corvus vm stop — end the agent session only", file=sys.stderr)
    if running:
        print("The isolated agent will shut down.", file=sys.stderr)
    else:
        print("There is no agent session running.", file=sys.stderr)
    print("Corvus-Node stays ready in the background.", file=sys.stderr)
    print("You can corvus vm start again without reinstalling.", file=sys.stderr)
    print("Chat, if open, will disconnect.", file=sys.stderr)
    print(
        "This does not shut Corvus-Node down. Use corvus stop for that.",
        file=sys.stderr,
    )


def _print_product_stop_explain(*, vm_up: bool, systemd: bool) -> None:
    print("corvus stop — shut Corvus-Node down", file=sys.stderr)
    print(
        "  1. The isolated agent" + (" will shut down." if vm_up else " is already stopped."),
        file=sys.stderr,
    )
    if systemd:
        print(
            "  2. Corvus-Node in the background will stop.",
            file=sys.stderr,
        )
        print(
            "     Chat will not work until it is started again.",
            file=sys.stderr,
        )
        print("Start again with: ./install.sh", file=sys.stderr)
        print("  (or sudo systemctl start corvus-node)", file=sys.stderr)
        print(
            "A password may be asked because isolation is a system job.",
            file=sys.stderr,
        )
        print("You are not giving the agent an admin account.", file=sys.stderr)
    else:
        print("  2. Corvus-Node in the background will stop.", file=sys.stderr)
    print(
        "To end only the agent session and leave Corvus-Node ready: corvus vm stop",
        file=sys.stderr,
    )


def _systemd_main_pid() -> int | None:
    try:
        proc = subprocess.run(
            ["systemctl", "show", "-p", "MainPID", "--value", SYSTEMD_UNIT],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        pid = int((proc.stdout or "").strip() or "0")
    except ValueError:
        return None
    return pid if pid > 0 else None


def _uses_this_systemd_unit(node: int | None) -> bool:
    """Stop systemd only when this CLI is talking to that unit's process."""
    main = _systemd_main_pid()
    if main is None:
        return False
    if node is not None and node > 0:
        return main == node
    return runtime_dir().resolve() == (product_prefix() / "run").resolve()


def _print_replace_stop_explain(*, why: str, vm_up: bool, systemd: bool) -> None:
    print(f"corvus {why} — Corvus-Node is already running", file=sys.stderr)
    print(
        "  1. The isolated agent" + (" will shut down." if vm_up else " is already stopped."),
        file=sys.stderr,
    )
    print(
        "  2. Corvus-Node in the background will stop so files can be replaced.",
        file=sys.stderr,
    )
    if why == "update":
        print("  3. The newer release is installed.", file=sys.stderr)
        print("  4. Corvus-Node starts again.", file=sys.stderr)
    else:
        print("  3. Install continues, then Corvus-Node starts again.", file=sys.stderr)
    print("A password may be asked because isolation is a system job.", file=sys.stderr)


def _stop_systemd_unit() -> int:
    cmd = ["systemctl", "stop", SYSTEMD_UNIT]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    print(
        "corvus: stopping Corvus-Node (password: isolation is a system job)",
        file=sys.stderr,
    )
    try:
        return subprocess.run(cmd, check=False).returncode
    except FileNotFoundError:
        return 127


def _start_systemd_unit() -> int:
    cmd = ["systemctl", "start", SYSTEMD_UNIT]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    print(
        "corvus: starting Corvus-Node (password: isolation is a system job)",
        file=sys.stderr,
    )
    try:
        return subprocess.run(cmd, check=False).returncode
    except FileNotFoundError:
        return 127


def _pip_upgrade(ref: str) -> int:
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", ref],
        check=False,
    ).returncode


def _execute_product_stop() -> int:
    """Stop guest then Node. Caller already confirmed."""
    pid = node_pid()
    systemd = _uses_this_systemd_unit(pid)
    if pid is None and not systemd:
        print("corvus: Corvus-Node is already stopped", file=sys.stderr)
        return 0
    if pid is not None:
        try:
            rpc_stop()
            print("corvus: agent session ended", file=sys.stderr)
        except ControlError as exc:
            print(f"corvus: agent session: {exc}", file=sys.stderr)
    if systemd:
        rc = _stop_systemd_unit()
        if rc != 0:
            print(
                "corvus: Corvus-Node did not stop; it may still be up "
                "(sudo systemctl stop corvus-node)",
                file=sys.stderr,
            )
            return 2
        wait_node_gone()
        print("corvus: Corvus-Node stopped", file=sys.stderr)
        return 0
    if node_pid() is not None:
        try:
            rpc_shutdown()
        except ControlError as exc:
            print(f"corvus: {exc}", file=sys.stderr)
            return 2
    print("corvus: Corvus-Node stopped", file=sys.stderr)
    return 0


def _vm_stop(*, yes: bool) -> int:
    pid = node_pid()
    if pid is None:
        print(f"corvus: {INSTALL_HINT}", file=sys.stderr)
        return 2
    running = _vm_is_running(pid)
    _print_vm_stop_explain(running=running)
    if not _confirm("End the agent session? Corvus-Node will stay ready.", yes=yes):
        print("corvus: cancelled", file=sys.stderr)
        return 2
    try:
        rpc_stop()
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    if running:
        print("corvus: agent session ended; Corvus-Node stays ready", file=sys.stderr)
    else:
        print("corvus: no agent session was running; Corvus-Node stays ready", file=sys.stderr)
    return 0


def _product_stop(*, yes: bool) -> int:
    pid = node_pid()
    systemd = _uses_this_systemd_unit(pid)
    if pid is None and not systemd:
        print("corvus: Corvus-Node is already stopped", file=sys.stderr)
        return 0
    _print_product_stop_explain(vm_up=_vm_is_running(pid), systemd=systemd)
    if not _confirm("Shut down the agent and Corvus-Node?", yes=yes):
        print("corvus: cancelled", file=sys.stderr)
        return 2
    rc = _execute_product_stop()
    if rc == 0 and systemd:
        print(
            "corvus: start again with corvus start (or sudo systemctl start corvus-node)",
            file=sys.stderr,
        )
    return rc


def _stop_running_for_replace(*, yes: bool, why: str) -> tuple[int, bool]:
    """If Node is up, confirm and stop it. Returns (code, restarted_later)."""
    pid = node_pid()
    systemd = _uses_this_systemd_unit(pid)
    if pid is None and not systemd:
        return 0, False
    _print_replace_stop_explain(why=why, vm_up=_vm_is_running(pid), systemd=systemd)
    prompt = (
        "Stop Corvus-Node, then continue the update?"
        if why == "update"
        else "Stop Corvus-Node, then continue install?"
    )
    if not _confirm(prompt, yes=yes):
        print("corvus: cancelled; Corvus-Node is still running", file=sys.stderr)
        return 2, False
    rc = _execute_product_stop()
    return rc, systemd and rc == 0


def _update(*, yes: bool) -> int:
    status = check_version()
    sys.stdout.write(format_version_status(status))
    if not status.update_available or not status.github:
        return 0
    print(
        f"Installed: {status.local}. GitHub release: {status.github}.",
        file=sys.stderr,
    )
    print("Say no to keep the version you have.", file=sys.stderr)
    if not _confirm(f"Upgrade to GitHub release {status.github}?", yes=yes):
        print(f"corvus: keeping {status.local}", file=sys.stderr)
        return 0
    stop_rc, restart = _stop_running_for_replace(yes=yes, why="update")
    if stop_rc != 0:
        return stop_rc
    ref = github_install_ref(status.github)
    print(f"corvus: installing GitHub release wheel {ref}", file=sys.stderr)
    pip_rc = _pip_upgrade(ref)
    if pip_rc != 0:
        print(
            "corvus: pip failed; sudo corvus update (installs the GitHub release wheel)",
            file=sys.stderr,
        )
        if restart:
            print(
                "corvus: Corvus-Node is down; ./install.sh (or sudo systemctl start corvus-node)",
                file=sys.stderr,
            )
        return pip_rc
    if restart:
        start_rc = _start_systemd_unit()
        if start_rc != 0:
            print(
                "corvus: updated, but Corvus-Node did not start (./install.sh)",
                file=sys.stderr,
            )
            return start_rc
        print("corvus: updated; Corvus-Node started", file=sys.stderr)
        return 0
    print("corvus: updated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
