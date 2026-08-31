**Document:** OPERATIONS.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OVERVIEW.md, AGENT-WORKFLOW.md, POLICY.md, ROADMAP.md, CHANGES.md, SECURITY.md
**Must Update on Change:** CHANGES.md

# Operations

## First run (operator)

Linux with KVM. Sudo only when the installer needs it. Group `corvus` is entered for you.

```bash
./install.sh
corvus status
corvus vm start
corvus chat
corvus vm stop
```

`./install.sh` installs missing packages, bakes the guest disk, and installs Node under `$HOME/Corvus-Node`. It puts `corvus` on PATH (`/usr/local/bin/corvus`); the command uses group `corvus` automatically (no `newgrp`). Re-runs skip green already-up-to-date steps. If Node is already running, the installer explains and asks before shutting it down (guest then systemd), then continues and starts Node again. The end of the installer prints a **Status** block (`corvus status --brief`: Node and VM only) then **You're set**. `vm stop` shuts down the guest VM (confirmation); the Node systemd unit stays up. `corvus stop` shuts down the guest then Node (confirmation; sudo for systemd). If Node is down, `vm` / `chat` fail closed.

Make path (same privileged inner script): `make check`, `make guest-assets`, `sudo make install`. Product overview: [README.md](../../README.md).

## Dev loop (no VM)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
make lint
```

Unit tests pair Node and guest over an anonymous socket. That pairing is **test-only**. It is not `corvus run`. New tools and LLM-facing behavior must be wired through `StubLlm` and `tests/test_stub.py` before a provider exists.

Every version ships a runnable operator CLI. `corvus --help` and `corvus status` describe **this build**. A verb that is not implemented fails closed with the version id.

## Install (sudo once)

```bash
./install.sh
# or: make guest-assets && sudo make install
corvus status
corvus vm start
```

Install creates group `corvus`, a venv at `$HOME/Corvus-Node/venv` (`root:corvus`, not user-writable), `$HOME/Corvus-Node/bin/corvus`, env at `$HOME/Corvus-Node/env`, hashed assets under `$HOME/Corvus-Node/assets`, control socket under `$HOME/Corvus-Node/run`, and systemd `corvus-node.service`. Firecracker **jail** dirs stay `/var/lib/corvus-node` (short vsock paths; `/run` is `nodev`). After `./install.sh` the operator CLI does not use sudo. Jailer still runs inside the Node service as root. The installer enters group `corvus` in that terminal.

`corvus update` refreshes that **installed** prefix from a newer GitHub tag (`pip` into `$HOME/Corvus-Node/venv`). It does not `git pull` this tree. If Node is running it explains, confirms, shuts down the guest and Node, then installs, then starts Node again (`--yes` skips the prompt). Sudo is needed because that venv is root-owned and because stopping/starting systemd is a root unit. If you are on a dirty checkout, ahead of `origin/main`, or a version newer than GitHub (typical internal run before a PR merges — local `0.1.6`, GitHub still `0.1.5`), it reports unreleased and does not install. `status` always prints the same check. An empty tags list is **no GitHub tags yet**, not unreachable. Tests set `CORVUS_NODE_SKIP_UPDATE_CHECK=1`.

## Guest assets

```bash
make guest-assets
```

Writes a pinned Firecracker **v1.16.1** binary, **jailer**, CI kernel, and Debian bookworm ext4 to `.cache/corvus-node/` (gitignored). Kernel, VMM, and jailer are SHA-256 verified on fetch and again on every `corvus vm start` / `run`. Bake needs `curl` and `mkfs.ext4`, plus one of `mmdebstrap`, `debootstrap`, or `docker` for the rootfs (skipped if `rootfs.ext4` already exists unless `CORVUS_NODE_FORCE_ROOTFS=1`). After a guest runtime/tool change, refresh the Python payload without a Debian rebuild: `CORVUS_NODE_REFRESH_PAYLOAD=1 make guest-assets` (needs `debugfs`). After bake, `rootfs.ext4.sha256` is written beside the image.

Override paths with `CORVUS_NODE_KERNEL`, `CORVUS_NODE_ROOTFS`, `CORVUS_NODE_FIRECRACKER`, `CORVUS_NODE_JAILER`, and `CORVUS_NODE_CACHE`. Details: `guest/README.md`.

Live KVM smoke boots a jailed microVM **through the installed Node** (no sudo, no spawned `serve`). Node must already be up (`./install.sh`). `make test` stays VM-free.

```bash
make smoke
# same as: CORVUS_NODE_SMOKE=1 pytest tests/test_kvm_smoke.py -q
```

Skip if the Node service is down, or if a guest VM is already running (`corvus vm stop` first). Isolation assets are the service's (`$HOME/Corvus-Node/env`), not the test process.

Jail dirs live under `/var/lib/corvus-node/firecracker/<id>/` (ext4, not `/run` — `/run` is `nodev` and jailer's `/dev/kvm` would fail with EACCES). The host vsock UDS is `{jail_root}/v.sock_4040` and must fit Linux `sockaddr_un` (107 bytes). Jailer `--new-pid-ns` clone()s Firecracker and the parent jailer exits 0; Node waits on `{jail_root}/firecracker.pid`. Kernel, rootfs, vsock UDS, `vm.json`, `fc.log`, and `serial.log` in the jail are copies owned by the jailer uid (a hardlink would chown the host asset). Jailer stdio is not the operator TTY (`stdin` is `/dev/null`; guest `ttyS0` is `serial.log`).

The operator control socket is `{runtime}/control.sock` (`0660`, group `corvus`). Default runtime is `$HOME/Corvus-Node/run`. Override with `CORVUS_NODE_RUNTIME_DIR`. PID file `node.pid`, serve log `node.log`.

## Operator CLI

Hashed kernel, rootfs, jailer, Firecracker, and KVM are required for a guest VM. The **CLI** does not need root after install.

```bash
corvus status
corvus vm start
corvus chat
corvus vm stop
corvus stop
corvus run --once "hello"
corvus run --once --tools echo "hello"
corvus vm start --workspace /path/to/tree --tools file_read,file_write
corvus update
```

If the Node service is not running, `vm` / `chat` **fail closed** (`./install.sh`). `status` still runs and shows `Node: down`. There is no TCP fallback and no raw Firecracker.

Default vsock port: `4040`. Guest CID is assigned at launch. `--workspace /path` is a live host directory Node may read and write after RBAC (one path). The guest does not mount that folder. Writes land on the host immediately. A later turn, or your editor, sees the same files.

Launch rules also live in `$XDG_CONFIG_HOME/corvus-node/launch.json` (`settings set` / `unset`). CLI flags override the file for that invocation. A running VM is not hot-patched; `vm stop` then `vm start` to apply.

```bash
corvus run --once --workspace /path/to/tree --tools file_read "review notes.txt"
corvus run --once --workspace /path/to/tree --tools file_write "edit notes.txt to 'done'"
```

`run --once "hello"` is one chat turn then exit. If the Node service is up it uses that VM path; if you are root and the service is down (legacy smoke) it still runs in-process. `vm start` boots a guest on the idle Node service. `corvus vm stop` shuts down the guest only (`session_end`, then reap jailer; confirmation; Node stays idle). `corvus stop` does that, then stops the Node systemd unit (confirmation; sudo for `systemctl stop`). `vm status` is the guest only. `status` leads with Node and VM, then this preview, version, and isolation (`--brief` is Node and VM only). `chat` is a live session: sticky header (model, context placeholder, `/exit`), conversation until `/exit`. `--tools` is an operator allow rule, not a filter bypass. See [POLICY.md](../architecture/POLICY.md).

`start` is an alias of `vm start`. `--yes` / `-y` skips the confirmation on `vm stop`, `stop`, and `update`.

Unit tests do not boot a VM.

Audit JSONL is written under `$XDG_STATE_HOME/corvus-node/audit/` (default `~/.local/state/corvus-node/audit/`), not in the jail directory.

## Metrics / fleet

Not in this product. Use Corvus Hypervisor later for a control plane.

**Black Rain Labs - Research & Development Division**
