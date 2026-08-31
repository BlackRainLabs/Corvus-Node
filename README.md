# Corvus-Node

Single-agent harness: **Node** on the host, four engines in one Firecracker VM, **AF_VSOCK** between them.

CLI/GUI talks only to Node. Node owns the workspace allowlist. Engines never sit on the host.

**Version:** 0.1.5 · **License:** [AGPLv3](LICENSE) · **Org:** Black Rain Labs — Research & Development Division

## Why

Security-first harness for **one** agent:

- **Star topology** — engines never talk to each other or the outside world
- **No LLM-to-tool bypass** — Engine 3 cannot call tools or memory
- **Deterministic policy** — RBAC baked into Node; chat-only unless you add a rule; no LLM inspection on the host
- **Isolation** — one Firecracker guest; Node reads and writes allowlisted host directories after RBAC

## Architecture

```
         CLI / GUI
              |
     host AF_UNIX (0660, group corvus)
              |
            Node  --------  Allowed workspaces / directories
              |
           AF_VSOCK
              |
    +---- Firecracker VM ----+
    | E1 tools  E2 channels  |
    | E3 LLM    E4 memory    |
    +------------------------+
```

Deep dive: [Architecture Overview](docs/architecture/OVERVIEW.md) · [Agent Workflow](docs/architecture/AGENT-WORKFLOW.md) · [Policy](docs/architecture/POLICY.md)

## Requirements

- Python **≥ 3.12**
- Linux
- To **run a turn**: install once with sudo (systemd Node + group `corvus`), KVM (`/dev/kvm`), jailer, Firecracker, a guest rootfs (see [OPERATIONS](docs/planning/OPERATIONS.md)). Daily `start` / `chat` / `stop` do not use sudo.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make test          # unit tests (no VM)
make lint
make guest-assets  # kernel + rootfs + firecracker + jailer into .cache/corvus-node/
```

A real session (sudo **once** to install, then no sudo):

```bash
make guest-assets
sudo make install          # /opt/corvus-node + systemd Node; log out/in or newgrp corvus
corvus status
corvus vm start
corvus chat
corvus vm stop
corvus run --once "hello"
corvus update         # installed app only; no-op on a local unreleased tree
```

Without the Node service, `vm` / `chat` / `run` fail closed (`sudo make install`). `status` still prints Node vs VM, isolation gaps, and the GitHub version check. Optional `--tools echo` asks the stub LLM for an Engine 1 echo after RBAC. `--workspace /path --tools file_read` lets Node read that live directory after RBAC. `settings` stores launch rules under `$XDG_CONFIG_HOME/corvus-node/launch.json`. `chat` is a live session until `/exit`; `vm stop` ends the guest VM (the Node service stays up). Guest kernel serial is not attached to the terminal.

## Status (v0.1.5 — Operator CLI)

Jailer-required launch, hashed assets, slim non-root guest, live `--workspace` file I/O on Node, operator CLI (`vm start` / `chat` / `vm stop` / `status` / `settings` / `update`) on one VM, host-minted hop key, bound tool results, durable audit. Sudo is for install. More tools, skills, provider LLMs, and Engine 4 persistence are later.

## License

Copyright (C) 2026 Black Rain Labs.

Corvus-Node is free software under the [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later). If you modify it and run it as a network service, AGPL section 13 requires you to offer the corresponding source to those users.

**Black Rain Labs - Research & Development Division**
