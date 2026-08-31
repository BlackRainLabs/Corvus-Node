**Document:** OPERATIONS.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OVERVIEW.md, AGENT-WORKFLOW.md, POLICY.md, ROADMAP.md, CHANGES.md, SECURITY.md
**Must Update on Change:** CHANGES.md

# Operations

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
make guest-assets
sudo make install
newgrp corvus   # or log out and back in
corvus status
corvus vm start
```

Install creates group `corvus`, a venv at `/opt/corvus-node/venv`, `/usr/local/bin/corvus`, `/etc/corvus-node/env`, copies guest assets into `/var/lib/corvus-node/assets` when present, and enables systemd `corvus-node.service` (root `serve`). The control socket is `0660` root:corvus. After that the operator CLI does not use sudo. Jailer still runs inside the Node service as root.

`corvus update` refreshes that **installed** prefix from a newer GitHub tag (`pip` into `/opt/corvus-node/venv`). It does not `git pull` this tree. Sudo is only needed if the prefix is not writable (same as reinstall). If you are on a dirty checkout, ahead of `origin/main`, or a version newer than GitHub (typical internal run before a PR merges — local `0.1.5`, GitHub still `0.1.4`), it reports unreleased and does not install. `status` always prints the same check. Tests set `CORVUS_NODE_SKIP_UPDATE_CHECK=1`.

## Guest assets

```bash
make guest-assets
```

Writes a pinned Firecracker **v1.16.1** binary, **jailer**, CI kernel, and Debian bookworm ext4 to `.cache/corvus-node/` (gitignored). Kernel, VMM, and jailer are SHA-256 verified on fetch and again on every `corvus vm start` / `run`. Bake needs `curl` and `mkfs.ext4`, plus one of `mmdebstrap`, `debootstrap`, or `docker` for the rootfs (skipped if `rootfs.ext4` already exists unless `CORVUS_NODE_FORCE_ROOTFS=1`). After a guest runtime/tool change, refresh the Python payload without a Debian rebuild: `CORVUS_NODE_REFRESH_PAYLOAD=1 make guest-assets` (needs `debugfs`). After bake, `rootfs.ext4.sha256` is written beside the image.

Override paths with `CORVUS_NODE_KERNEL`, `CORVUS_NODE_ROOTFS`, `CORVUS_NODE_FIRECRACKER`, `CORVUS_NODE_JAILER`, and `CORVUS_NODE_CACHE`. Details: `guest/README.md`.

Live KVM smoke boots a jailed microVM **through the installed Node** (no sudo, no spawned `serve`). Node must already be up (`sudo make install`). `make test` stays VM-free.

```bash
make smoke
# same as: CORVUS_NODE_SMOKE=1 pytest tests/test_kvm_smoke.py -q
```

Skip if the Node service is down, or if a guest VM is already running (`corvus vm stop` first). Isolation assets are the service's (`/etc/corvus-node/env`), not the test process.

Jail dirs live under `/var/lib/corvus-node/firecracker/<id>/` (ext4, not `/run` — `/run` is `nodev` and jailer's `/dev/kvm` would fail with EACCES). The host vsock UDS is `{jail_root}/v.sock_4040` and must fit Linux `sockaddr_un` (107 bytes). Jailer `--new-pid-ns` clone()s Firecracker and the parent jailer exits 0; Node waits on `{jail_root}/firecracker.pid`. The vsock UDS, `vm.json`, `fc.log`, and `serial.log` are owned by the jailer uid. Jailer stdio is not the operator TTY (`stdin` is `/dev/null`; guest `ttyS0` is `serial.log`).

The operator control socket is `{runtime}/control.sock` (`0660`, group `corvus`). Default runtime is `/var/lib/corvus-node`. Override with `CORVUS_NODE_RUNTIME_DIR`. PID file `node.pid`, serve log `node.log`.

## Operator CLI

Hashed kernel, rootfs, jailer, Firecracker, and KVM are required for a guest VM. The **CLI** does not need root after install.

```bash
corvus status
corvus vm start
corvus chat
corvus stop
corvus vm stop
corvus run --once "hello"
corvus run --once --tools echo "hello"
corvus vm start --workspace /path/to/tree --tools file_read,file_write
corvus update
```

If the Node service is not running, `vm` / `chat` **fail closed** (`sudo make install`). `status` still runs and shows `Node: down`. There is no TCP fallback and no raw Firecracker.

Default vsock port: `4040`. Guest CID is assigned at launch. `--workspace /path` is a live host directory Node may read and write after RBAC (one path). The guest does not mount that folder. Writes land on the host immediately. A later turn, or your editor, sees the same files.

Launch rules also live in `$XDG_CONFIG_HOME/corvus-node/launch.json` (`settings set` / `unset`). CLI flags override the file for that invocation. A running VM is not hot-patched; `vm stop` then `vm start` to apply.

```bash
corvus run --once --workspace /path/to/tree --tools file_read "review notes.txt"
corvus run --once --workspace /path/to/tree --tools file_write "edit notes.txt to 'done'"
```

`run --once "hello"` is one chat turn then exit. If the Node service is up it uses that VM path; if you are root and the service is down (legacy smoke) it still runs in-process. `vm start` boots a guest on the idle Node service. `corvus stop` / `vm stop` always shut down the guest VM first (`session_end`, then reap jailer); the Node service stays idle. `vm status` is the guest only. `status` prints Node and VM as separate lines. `chat` is a live session: sticky header (model, context placeholder, `/exit`), conversation until `/exit`. `--tools` is an operator allow rule, not a filter bypass. See [POLICY.md](../architecture/POLICY.md).

`start` / `stop` are aliases of `vm start` / `vm stop`. They do not start or stop the Node systemd unit.

Unit tests do not boot a VM.

Audit JSONL is written under `$XDG_STATE_HOME/corvus-node/audit/` (default `~/.local/state/corvus-node/audit/`), not in the jail directory.

## Metrics / fleet

Not in this product. Use Corvus Hypervisor later for a control plane.

**Black Rain Labs - Research & Development Division**
