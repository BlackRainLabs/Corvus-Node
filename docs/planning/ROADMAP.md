**Document:** ROADMAP.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** CHANGES.md, OPERATIONS.md, OVERVIEW.md, POLICY.md, SECURITY.md
**Must Update on Change:** CHANGES.md

# Roadmap

## Now (v0.1.6 — guided installer)

- `./install.sh` into `$HOME/Corvus-Node` (idempotent; sudo only when needed; `corvus` on PATH uses group `corvus` automatically)
- Operator CLI command is `corvus` (`vm start|stop|status`, `chat`, `status`, `settings`, `run --once`, `update`)
- `corvus vm stop` shuts down the guest only (confirmation; Node stays up). `corvus stop` shuts down the guest then Node (confirmation; sudo for systemd)
- Host AF_UNIX control socket (group `corvus`); guest stays AF_VSOCK
- Firecracker jail dirs stay `/var/lib/corvus-node` (vsock path limit)
- Version check vs GitHub **releases** (wheel); unreleased local trees do not update from GitHub
- `./install.sh` from a git checkout (or unpacked snapshot with `src/`) uses this tree; `--release` / `corvus update` use the GitHub release wheel (upgrade or keep)
- Each version ships `--help` / `status` that name this build; unimplemented verbs fail closed
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
- GUI (Qt/QML operator window) on the same Node control socket
- Social gateways (Telegram, WhatsApp) binding principals on Node
- Hypervisor as fleet dash for many Corvus-Node instances

**Black Rain Labs - Research & Development Division**
