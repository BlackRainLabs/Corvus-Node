**Document:** OVERVIEW.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** AGENT-WORKFLOW.md, POLICY.md, OPERATIONS.md, CHANGES.md, SECURITY.md
**Must Update on Change:** CHANGES.md
**AI Instruction:** When revising this document, review Core Principles & Invariants here, update CHANGES.md, and do not contradict core fundamentals. Architecture graph: CLI/GUI → host AF_UNIX → Node → allowed workspaces; Node → AF_VSOCK → Firecracker VM (E1–E4). No supervisor box.

# Corvus-Node Architecture Overview

**Status:** Current — v0.1.6 guided installer
**Organization:** Black Rain Labs
**Division:** Research & Development Division

## v0.1.6 graph (authoritative)

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

**Node** is Corvus-Node on the **host**. The four engines live **only** inside the microVM. There is no supervisor component in this product. CLI is the firewall console: it writes rules; every hop is still filtered and MAC-checked. Launch is **jailer-only** (fail closed). The guest payload is not the host TCB.

## Core Principles & Invariants (Authoritative)

These principles must be respected across all documents and code:

1. **Everything crosses Node** — CLI/GUI never talks to engines or Firecracker except through Node. Node mediates RBAC, audit, LLM credentials, memory, and workspace file I/O.
2. **Strict star topology** — Engines have no direct external or inter-engine communication. Their only path off the guest is **AF_VSOCK to Node**.
3. **No direct LLM-to-tool execution** — Engine 3 cannot call tools or access memory. Tool and memory hops go to Node for validation.
4. **Deterministic validation only** — Node performs **no LLM-based semantic inspection**. Validation uses structured metadata, correlation ids, capability tags, and allowlists.
5. **Launch-time immutability** — Tools and the workspace allowlist are selected at launch. Changing them requires a new microVM.
6. **Host-owned memory** — Persistent memory lives on the host (Node). v1 is a `private` namespace for this one identity. Engine 4 is the guest client.
7. **Full auditability of every hop** — Every message is logged with correlation ids. Audit is durable on the host (hash-chained JSONL), not in the guest and not in the jail instance dir.
8. **4-engine model** — The Firecracker VM contains exactly four engines (tools, channels, LLM, memory). v0.1.6 still runs them in one guest process. `source_engine` is a claim; hop MAC does not authenticate a pwned guest.
9. **Default deny, chat implicit** — RBAC is baked into Node. Basic LLM chat is allowed; anything else is an added rule or elevation. CLI writes rules; it does not skip the filter.
10. **Hop integrity** — Host mints the hop key (`session_init`). Later vsock envelopes carry seq + HMAC bound to `vm_instance_id`. Mid-path alteration is dropped and flagged. HMAC does not prove user intent.
11. **Jailer is the VMM path** — The Node **service** (`corvus serve`, systemd) requires root, jailer, KVM, and hashed kernel/rootfs/Firecracker/jailer. Install is `./install.sh` (sudo when needed) into `$HOME/Corvus-Node`; a git checkout installs that tree, `corvus update` is the GitHub release wheel. Jail chroots stay `/var/lib/corvus-node`. The operator CLI (`start` / `vm start` / `chat` / `vm stop`) talks to Node over host AF_UNIX and does not use sudo. `corvus start` brings Node up and asks before starting the guest (Enter skips the VM). `vm start` starts the guest with no extra prompt. `vm stop` shuts down the guest only (confirmation; Node stays up). `corvus stop` shuts down the guest then the Node systemd unit (confirmation; sudo for `systemctl stop`). No raw Firecracker. No TCP product mode.
12. **Slim guest** — The image contains protocol, runtime, tools, and the guest entry. Host Node, policy, LLM keys, audit, and launcher are not copied into the VM.

## Product

Corvus-Node is a **single-agent** harness. v0.1.6 ships a guided installer (`./install.sh` from a checkout installs that tree; `corvus update` is the GitHub release wheel) and the **operator CLI** (`start` / `vm start` / `chat` / `vm stop` / `status` / `settings` / `run --once` / `update`) at the same layer a GUI will use later: a thin client of Node. Node owns jailer, vsock, RBAC, and the control socket. Social gateways (Telegram, WhatsApp) identify principals on Node later. A fleet control plane is Corvus Hypervisor — later, not a box in this graph. Host-root / SEV-SNP is out of scope: if the box is owned, RAM dumps win.

Allowed workspaces are attached to **Node**. `--workspace /path` is a live host directory Node may read and write after RBAC. File tools use `/workspace` paths that Node maps onto that tree. The rest of the host is invisible. The guest does not mount the host folder.

## Transport

Node ↔ guest is **AF_VSOCK** only. CLI/GUI ↔ Node is **host AF_UNIX** (control socket, `0660`, group `corvus`). The Node service without KVM/vsock/jailer/root fails closed. There is no TCP product mode. Envelope version **1.1** (seq, payload hash, MAC). Session key is host-minted on `session_init`, never on the kernel cmdline.

## Major components

- **CLI / GUI** — operator surface for this one agent (CLI is the console that writes rules; same layer as a later GUI)
- **Node (host)** — Corvus-Node: firewall policy, principals, hop MAC, durable audit, LLM gateway, memory store, workspace allowlist, jailer launch, vsock, operator control socket, channel adapters
- **Allowed workspaces** — host directories Node may read and write after RBAC; not a free view of the machine
- **Firecracker VM** — isolation boundary, started only via jailer
- **Engines (guest)** — E1 tools, E2 channels, E3 LLM client, E4 memory client (non-root after mounts)

Policy details: [POLICY.md](POLICY.md). Threat model: [SECURITY.md](../../SECURITY.md).

**Black Rain Labs - Research & Development Division**
