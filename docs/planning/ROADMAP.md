**Document:** ROADMAP.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** CHANGES.md, OPERATIONS.md, OVERVIEW.md, POLICY.md, SECURITY.md
**Must Update on Change:** CHANGES.md

# Roadmap

## Now (v0.1.9 — start after stop)

- `./install.sh` into `$HOME/Corvus-Node` (idempotent; sudo only when needed; `corvus` on PATH uses group `corvus` automatically)
- First-install bake works on Ubuntu/Kubuntu (`mktemp` unpack, Debian archive keyring, payload copy without host pydantic)
- Operator CLI command is `corvus` (`start`, `vm start|stop|status`, `chat`, `gui`, `status`, `settings`, `run --once`, `update`)
- `corvus start` brings Node up and asks before the guest (Enter skips the VM). `corvus vm stop` shuts down the guest only (confirmation; Node stays up). `corvus stop` shuts down the guest then Node (confirmation; sudo for systemd). After `corvus stop`, start again with `corvus start` (not `./install.sh`)
- `corvus gui` splash (PySide6). Fail-closes if Qt/PySide is missing. Does not talk to Node. Does not write launch rules
- Installer tries PySide6 (optional extra) and host xcb/EGL/fontconfig libs; a miss does not abort (CLI stays). `corvus update` upgrades the wheel, then tries GUI extras
- Releases ship `gui/corvus_gui/` only (not REQUESTS.md or GUI workflow docs)
- GUI/core contract: `docs/gui/AVAILABLE.md` (core) and `gui/REQUESTS.md` (GUI team)
- Host AF_UNIX control socket (group `corvus`); guest stays AF_VSOCK
- Firecracker jail dirs stay `/var/lib/corvus-node` (vsock path limit)
- Version check vs GitHub **releases** (wheel); unreleased local trees do not update from GitHub
- `./install.sh` from a git checkout (or unpacked snapshot with `src/`) uses this tree; `--release` / `corvus update` use the GitHub release wheel (upgrade or keep)
- Each version ships `--help` / `status` that name this build; unimplemented verbs fail closed
- Each new version is a GitHub Release (wheel + install tarball) via `.github/workflows/release.yml` on merge to `main` or a `v*` tag. Bump only when operators should get a batch; later merges on the same version do not replace the wheel.
- Live host workspace, jailer, hop MAC, RBAC, stub chat
- Unit tests without a VM (`make test`); installed-Node KVM smoke (`make smoke`)

## Next

More tools, stub-first (`StubLlm` + `tests/test_stub.py`). Do not wait for a provider.

## Later

- Skills in-guest after host allow
- Real LLM provider behind Node (first live chat turn that is not the stub)
- Finish RBAC (elevation UX, remaining firewall gaps)
- Engine 4 durable `private` memory on the host
- Split E1 vs E3 as separate guest processes
- Polkit later. This version: `corvus` on PATH uses group `corvus` via `sg` (no `newgrp`)
- Full operator window (Qt) on the same Node control socket (after AVAILABLE + requests)
- Social gateways (Telegram, WhatsApp) binding principals on Node
- Hypervisor as fleet dash for many Corvus-Node instances

**Black Rain Labs - Research & Development Division**
