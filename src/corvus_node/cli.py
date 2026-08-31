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
)
from corvus_node.node.daemon import (
    AlreadyRunning,
    rpc_shutdown,
    rpc_start,
    rpc_status,
    rpc_stop,
    serve_forever,
    start_daemon,
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
    sub.add_parser("status", help="Node service, guest VM, isolation, version")
    start_p = sub.add_parser("start", help="boot the guest VM (alias of: vm start)")
    _launch_flags(start_p)
    sub.add_parser("chat", help="live chat until /exit")
    sub.add_parser("stop", help="shut down the guest VM (alias of: vm stop)")
    vm_p = sub.add_parser("vm", help="Firecracker guest (Node service stays up)")
    vm_sub = vm_p.add_subparsers(dest="vm_cmd", required=False)
    vm_start = vm_sub.add_parser("start", help="boot the jailed guest VM")
    _launch_flags(vm_start)
    vm_sub.add_parser("stop", help="shut down the guest VM")
    vm_sub.add_parser("status", help="guest VM only")
    sub.add_parser("update", help="install a newer GitHub release of the app")
    settings_p = sub.add_parser("settings", help="launch rules (tools, workspace)")
    settings_sub = settings_p.add_subparsers(dest="settings_cmd")
    set_p = settings_sub.add_parser("set", help="set a launch rule")
    set_p.add_argument("key", choices=["tools", "workspace"])
    set_p.add_argument("value")
    unset_p = settings_sub.add_parser("unset", help="clear a launch rule")
    unset_p.add_argument("key", choices=["tools", "workspace"])
    run_p = sub.add_parser("run", help="one-shot turn (no daemon)")
    run_p.add_argument(
        "--once",
        action="store_true",
        help="one user turn, then exit",
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
        return _status()
    if args.command == "settings":
        return _settings(args)
    if args.command == "chat":
        return _run_chat()
    if args.command == "stop":
        return _stop()
    if args.command == "vm":
        return _vm(args)
    if args.command == "update":
        return _update()
    try:
        merged = _merged_launch(args)
    except (WorkspaceError, SettingsError) as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    if args.command == "start":
        return _start(merged)
    if args.command == "serve":
        return _serve(merged)
    if args.command == "run":
        if not args.once or not args.text:
            print(f"corvus: v{__version__} requires: run --once TEXT", file=sys.stderr)
            return 2
        return _run_once(args.text, merged)
    print(f"corvus: unknown command {args.command}", file=sys.stderr)
    return 2


def _launch_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tools",
        default=None,
        help="comma-separated launch tools (overrides settings)",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        default=None,
        help="host directory Node may read/write (one path; overrides settings)",
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
            "Refusing to run without jailer/Firecracker/vsock (no TCP fallback).",
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


def _status() -> int:
    for line in build_lines():
        print(line)
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
    sys.stdout.write(format_version_status(check_version()))
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
        return _stop()
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
    print("corvus: guest VM started", file=sys.stderr)
    return 0


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
        print("corvus: guest VM is not running; corvus vm start", file=sys.stderr)
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


def _stop() -> int:
    try:
        rpc_stop()
    except ControlError as exc:
        print(f"corvus: {exc}", file=sys.stderr)
        return 2
    print("corvus: guest VM shut down", file=sys.stderr)
    return 0


def _update() -> int:
    status = check_version()
    sys.stdout.write(format_version_status(status))
    if not status.update_available or not status.github:
        return 0
    ref = github_install_ref(status.github)
    print(f"corvus: installing {ref}", file=sys.stderr)
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", ref],
        check=False,
    )
    if proc.returncode != 0:
        print(
            "corvus: pip failed; sudo corvus update (updating the installed app is a reinstall)",
            file=sys.stderr,
        )
        return proc.returncode
    try:
        rpc_shutdown()
    except ControlError:
        pass
    print("corvus: updated; Node service will restart if systemd is enabled", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
