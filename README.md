# Corvus-Node

**Corvus** is a security-first AI agent harness. One agent. One Firecracker microVM. The model never calls tools, never sees the rest of the host, and never skips policy — **Node** is the only door, and it is default-deny.

Talk to it with `corvus` on Linux. Isolation is the product, not a plugin.

v0.1.6 is under active development. This build uses a stub LLM so you can run the real jailer path today.

**Version:** 0.1.6 · **License:** [AGPLv3](LICENSE) · **Org:** Black Rain Labs — Research & Development Division

## Install and run

Linux (x86_64 or aarch64) with **KVM**. The installer installs missing packages, bakes the guest disk, and puts Node under **`$HOME/Corvus-Node`**. Sudo is only for jailer/KVM and root-owned files. The installer adds you to group `corvus` and enters that group in the same terminal.

```bash
git clone https://github.com/BlackRainLabs/Corvus-Node.git
cd Corvus-Node
./install.sh
```

Then:

```bash
corvus status
corvus vm start
corvus chat                # type a line, then /exit
corvus stop
```

Re-run `./install.sh` anytime: steps that are already good print green **already up to date**. `./install.sh --yes` skips “press Enter”. `make check` still lists host gaps. `sudo make install` remains the inner privileged step after a bake.

`corvus` lives at `$HOME/Corvus-Node/bin/corvus` (and `~/.local/bin/corvus` when that directory exists). Daily `vm` / `chat` / `stop` do **not** use sudo. If `corvus` says the Node service is not running, run `./install.sh` (or `sudo systemctl start corvus-node`).

### Daily commands

| Command | What it does |
| --- | --- |
| `corvus status` | Node service, guest VM, isolation gaps, version |
| `corvus vm start` | Boot the jailed guest (`start` is the same) |
| `corvus chat` | Live session until `/exit` (VM stays up) |
| `corvus stop` | Shut down the guest (`vm stop` is the same) |
| `corvus vm status` | Guest only |
| `corvus run --once "hello"` | One turn, then exit |
| `corvus update` | Newer GitHub tag into `$HOME/Corvus-Node` (not this git tree) |

Optional: `--tools echo` asks the stub for an Engine 1 echo after RBAC. `--workspace /path --tools file_read` lets Node read that live directory after RBAC. `corvus settings` stores launch rules under `$XDG_CONFIG_HOME/corvus-node/launch.json`. A running VM is not hot-patched; `stop` then `vm start` to apply new rules.

### If something fails

- `make check` still prints `need` lines — install those packages, enable virtualization, run it again.
- `corvus status` shows `Node: down` — `./install.sh` (or `sudo systemctl start corvus-node`).
- `Isolation: not ready` — `./install.sh` again so hashed assets land under `$HOME/Corvus-Node/assets`.
- `chat` / `vm` fail closed if Node is not running. That is intentional. There is no TCP mode.
- Permission denied on the control socket — run `./install.sh` so it can enter group `corvus` in this terminal.

More detail: [Operations](docs/planning/OPERATIONS.md).

## What this version does

Jailer-required launch, hashed assets, slim non-root guest, live `--workspace` file I/O on Node, operator CLI on one VM, host-minted hop key, bound tool results, durable audit. Sudo is for install.

**Not in this build:** a provider LLM, skills, durable Engine 4 memory, or a GUI. Unimplemented verbs fail closed with the version id.

## How it works

CLI/GUI talks only to **Node** on the host. Node owns the workspace allowlist, RBAC, and the Firecracker jailer. Four engines live **only** inside the guest. Engines never sit on the host.

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

- **Star topology** — engines never talk to each other or the outside world
- **No LLM-to-tool bypass** — Engine 3 cannot call tools or memory
- **Deterministic policy** — RBAC in Node; chat-only unless you add a rule
- **Isolation** — one Firecracker guest; Node reads and writes allowlisted host directories after RBAC

## Technical reference

- [Architecture overview](docs/architecture/OVERVIEW.md) — invariants (authoritative)
- [Agent workflow](docs/architecture/AGENT-WORKFLOW.md) — guest engines
- [Policy](docs/architecture/POLICY.md) — RBAC
- [Operations](docs/planning/OPERATIONS.md) — bake, install, smoke, paths
- [Security](SECURITY.md) — threat model
- [Roadmap](docs/planning/ROADMAP.md) — now / next / later
- [Guest image](guest/README.md) — kernel, rootfs, jailer
- [Changelog](CHANGES.md)

## Contribute

Patches are welcome. The product is still moving; read the invariants before changing behavior.

1. [CONTRIBUTING.md](CONTRIBUTING.md) — license, changelog, stub-first tests
2. [AGENTS.md](AGENTS.md) — layout and isolation rules for this tree
3. Dev loop (no VM): `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && make test && make lint`

Live KVM smoke is `make smoke` against the **installed** Node (`CORVUS_NODE_SMOKE=1`, no sudo). Skip if Node is down or a guest is already running.

## License

Copyright (C) 2026 Black Rain Labs.

Corvus-Node is free software under the [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later). If you modify it and run it as a network service, AGPL section 13 requires you to offer the corresponding source to those users.

**Black Rain Labs - Research & Development Division**
