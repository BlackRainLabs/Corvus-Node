**Document:** OPERATIONS.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OVERVIEW.md, AGENT-WORKFLOW.md, POLICY.md, ROADMAP.md, CHANGES.md, SECURITY.md, AVAILABLE.md
**Must Update on Change:** CHANGES.md

# Operations

## First run (operator)

Linux with KVM. Sudo only when the installer needs it. `corvus` uses group `corvus` via `sg` (no `newgrp`). Users unpack `corvus-node-install.tar.gz` from the [latest GitHub Release](https://github.com/BlackRainLabs/Corvus-Node/releases/latest) (not a git clone). Contributors run `./install.sh` from this checkout.

```bash
./install.sh
corvus status
corvus start              # Node; asks before the VM (Enter skips)
corvus vm start           # isolated agent, no extra prompt
corvus chat
corvus gui                # splash (this preview; does not talk to the agent)
corvus vm stop
```

`./install.sh` from a **git checkout** (or an unpacked release snapshot that still has `src/`) installs **this tree**. `--release`, or a directory with no Corvus-Node source, fetches the GitHub **release wheel**. The installer does **not** tell you GitHub has a newer version; `corvus status` and `corvus update` do that. If Corvus-Node is already installed, the installer asks to upgrade or keep the current version. It puts `corvus` on PATH (`/usr/local/bin/corvus`). Re-runs skip green already-up-to-date steps. If Node is already running **and** this run will replace files, the installer explains and asks before shutting it down (guest then systemd), then continues and starts Node again. The end of the installer prints a **Status** block (`corvus status --brief`: Node and VM only) then **You're set**. `vm stop` shuts down the guest VM (confirmation); the Node systemd unit stays up. `corvus stop` shuts down the guest then Node (confirmation; sudo for systemd). If Node is down, `vm` / `chat` fail closed.

Make path (same privileged inner script): `make check`, `make guest-assets`, `sudo make install`. Product overview: [README.md](../../README.md).

## Before merge (this checkout)

`make test` / `make lint` use a developer `.venv`. They do **not** update `$HOME/Corvus-Node`. The live guest talks to the **installed** Node.

```bash
make test
make lint
./install.sh          # this tree; say yes to upgrade if Corvus-Node is already installed
make smoke            # Node must be up; no guest already running
```

`make test` refuses a frozen `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`. Unset them before you commit. Do not copy those dates from an older commit when rewriting.

The product is **Corvus-Node**. `corvus` is only the operator CLI. Never call this product Corvus (a different creator's project). Commits and docs are **Black Rain Labs - Research & Development Division**. Strip Cursor / AI trailers (`Co-authored-by: Cursor`, Made by, Created by) with `packaging/strip-ai-trailers.sh`. Human GitHub Contributors are allowed. Do not add Cursor as an author.

Do not use `corvus update` or `./install.sh --release` to pick up uncommitted clone work.

## Deploy (every new version)

A new version is a GitHub Release (wheel + `corvus-node-install.tar.gz`). **Bump only when operators should get it** — not on every PR. Merge work to `main` at the current version; CI publishes `vX.Y.Z` the first time that version lands with no Release yet. Later merges on the same version do not replace the wheel. When you want operators to upgrade, bump `pyproject.toml`, `src/corvus_node/__init__.py`, and the README together in that PR. `corvus update` and `./install.sh --release` compare version numbers. Contributors pick up unreleased `main` with `./install.sh` from the clone. The wheel and tarball include GUI **runtime** (`gui/corvus_gui/`) only — not `gui/REQUESTS.md` or `docs/gui/`. Tagging `vX.Y.Z` by hand does the same.

Commits and Releases use the wall clock. CI unsets `GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`, and `SOURCE_DATE_EPOCH` before it builds the wheel and creates the Release. GitHub file listings use **author date**; a frozen stamp makes every touched file look hours old.

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
corvus start              # Node; asks before the VM (Enter skips)
corvus vm start
```

Install creates group `corvus`, a venv at `$HOME/Corvus-Node/venv` (`root:corvus`, not user-writable), `$HOME/Corvus-Node/bin/corvus`, env at `$HOME/Corvus-Node/env`, hashed assets under `$HOME/Corvus-Node/assets`, control socket under `$HOME/Corvus-Node/run`, and systemd `corvus-node.service`. `pip` then tries PySide6 (optional extra). The installer also tries host Qt libraries (xcb/EGL/fontconfig) on apt and dnf. If those GUI steps fail, the install continues; the CLI and Node stay available. `corvus gui` fail-closes until they are present. Firecracker **jail** dirs stay `/var/lib/corvus-node` (short vsock paths; `/run` is `nodev`). After `./install.sh` the operator CLI does not use sudo. Jailer still runs inside the Node service as root. `corvus` on PATH uses group `corvus` via `sg` (no `newgrp` at the end of install).

`corvus update` refreshes that **installed** prefix from a newer GitHub **release wheel** (`pip` into `$HOME/Corvus-Node/venv`). The wheel includes the GUI runtime (`corvus_gui`); PySide6 is optional. A failed GUI extra does not abort the update. It does not `git pull` this tree and it does not clone the repo. It asks to upgrade or keep the current version. If Node is running it then explains, confirms, shuts down the guest and Node, then installs, then starts Node again (`--yes` skips the prompts). Sudo is needed because that venv is root-owned and because stopping/starting systemd is a root unit. Host Qt libraries (xcb/EGL) are attempted by `./install.sh`, not by `corvus update`. If `corvus gui` fail-closes on missing OS libs, re-run `./install.sh`. If you are on a dirty checkout, ahead of `origin/main`, or a version newer than GitHub (typical internal run before a PR merges — local `0.1.7`, GitHub still `0.1.6`), it reports unreleased and does not install. `status` always prints the same check. No GitHub Release is **no GitHub release yet**, not unreachable. See **Deploy** above. Tests set `CORVUS_NODE_SKIP_UPDATE_CHECK=1`.

## Guest assets

```bash
make guest-assets
```

Writes a pinned Firecracker **v1.16.1** binary, **jailer**, CI kernel, and Debian bookworm ext4 to `.cache/corvus-node/` (gitignored). Kernel, VMM, and jailer are SHA-256 verified on fetch and again on every `corvus vm start` / `run`. Bake needs `curl` and `mkfs.ext4`, plus one of `mmdebstrap`, `debootstrap`, or `docker` for the rootfs (skipped if `rootfs.ext4` already exists unless `CORVUS_NODE_FORCE_ROOTFS=1`). `mmdebstrap` writes a tarball so a `0700` unpack directory (`mktemp -d`) does not fail unshare with Permission denied. On Ubuntu/Kubuntu, bake uses a pinned Debian archive keyring (`signed-by`) because Ubuntu apt keys do not verify bookworm. After a guest runtime/tool change, refresh the Python payload without a Debian rebuild: `CORVUS_NODE_REFRESH_PAYLOAD=1 make guest-assets` (needs `debugfs`). After bake, `rootfs.ext4.sha256` is written beside the image.

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
corvus start
corvus vm start
corvus chat
corvus gui
corvus vm stop
corvus stop
corvus run --once "hello"
corvus run --once --tools echo "hello"
corvus vm start --workspace /path/to/tree --tools file_read,file_write
corvus update
```

If the Node service is not running, `corvus start` brings it up (asks before the VM). `vm` / `chat` **fail closed** until Node is up. `status` still runs and shows `Node: down`. `corvus gui` does not need Node; it fail-closes if PySide/Qt is missing. There is no TCP fallback and no raw Firecracker.

Default vsock port: `4040`. Guest CID is assigned at launch. `--workspace /path` is a live host directory Node may read and write after RBAC (one path). The guest does not mount that folder. Writes land on the host immediately. A later turn, or your editor, sees the same files.

Launch rules also live in `$XDG_CONFIG_HOME/corvus-node/launch.json` (`settings set` / `unset`). CLI flags override the file for that invocation. A running VM is not hot-patched; `vm stop` then `vm start` to apply.

```bash
corvus run --once --workspace /path/to/tree --tools file_read "review notes.txt"
corvus run --once --workspace /path/to/tree --tools file_write "edit notes.txt to 'done'"
```

`run --once "hello"` is one chat turn then exit. If the Node service is up it uses that VM path; if you are root and the service is down (legacy smoke) it still runs in-process. `corvus start` brings Node up and asks before starting the guest (Enter skips the VM; `--yes` starts it). `vm start` boots a guest on the idle Node service with no extra prompt. `corvus vm stop` shuts down the guest only (`session_end`, then reap jailer; confirmation; Node stays idle). `corvus stop` does that, then stops the Node systemd unit (confirmation; sudo for `systemctl stop`). `vm status` is the guest only. `status` leads with Node and VM, then this preview, version, and isolation (`--brief` is Node and VM only). `chat` is a live session: sticky header (model, context placeholder, `/exit`), conversation until `/exit`. `corvus gui` is the splash (this preview). `--tools` is an operator allow rule, not a filter bypass. See [POLICY.md](../architecture/POLICY.md). GUI contract: [AVAILABLE.md](../gui/AVAILABLE.md).

`--yes` / `-y` skips the confirmation on `vm stop`, `stop`, and `update`, and on `start` it starts the VM without asking.

Unit tests do not boot a VM.

Audit JSONL is written under `$XDG_STATE_HOME/corvus-node/audit/` (default `~/.local/state/corvus-node/audit/`), not in the jail directory.

## Metrics / fleet

Not in this product. Use Corvus Hypervisor later for a control plane.

**Black Rain Labs - Research & Development Division**
