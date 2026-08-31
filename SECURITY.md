# Security Policy

**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31

## Threat model (v0.1.8)

- **Guest is hostile.** Tool code, a compromised model client, and the rest of the microVM are untrusted. Node is the policy point. Engines have no NIC.
- **Operator is trusted** to write launch rules (CLI). Those rules still go through the filter.
- **Host root is out of scope.** If this Linux box is owned, they dump RAM. SEV-SNP/TDX is a different product.

## What v0.1.8 claims

- No TCP product mode. Launch is jailer-only. Assets are SHA-256 checked on every run.
- The guest image does not contain host Node, policy, LLM, audit, or launcher.
- Hop HMAC stops mid-path alteration on vsock after `session_init`. It does **not** authenticate a pwned guest's `source_engine` claim.
- Audit is hash-chained JSONL on the host. Session keys are not persisted.
- `tool_result` must match an approved `tool_call`.
- `--workspace` is a live host directory Node may read and write after RBAC. File-tool paths stay under `/workspace`; Node flags `path_escape` and refuses symlinks. The guest does not mount the host tree.
- CLI/GUI talk to Node on a host AF_UNIX control socket (`0660`, group `corvus`). That protocol is not guest envelopes and not vsock. Sudo is for `./install.sh` (systemd Node, root-owned `$HOME/Corvus-Node` venv). The operator CLI does not run as root. `corvus` on PATH uses group `corvus` automatically (no `newgrp`).
- `corvus vm start` holds one jailed VM until `vm stop` (`session_end`). `corvus start` brings Node up and asks before the guest (Enter skips the VM; `--yes` starts it). `chat` is a live session until `/exit`; that detaches without tearing the VM down. `corvus vm stop` shuts down the guest only (confirmation; Node stays idle). `corvus stop` shuts down the guest then the Node systemd unit (confirmation; sudo for `systemctl stop`). `status` reports Node and VM separately.
- `corvus update` installs a newer GitHub **release wheel** into `$HOME/Corvus-Node` (the installed CLI; GUI extras if they install). It asks to upgrade or keep the current version. If Node is running it then confirms, shuts down the guest and Node, then pip-installs, then starts Node again. It refuses when the local tree is unreleased (dirty, ahead of origin, or version newer than GitHub), so internal pre-PR runs do not downgrade from GitHub. It does not `git pull` a checkout. `./install.sh` from a git tree installs that checkout and tries host Qt libraries; missing GUI deps do not abort the CLI/Node install. A version bump merged to `main` publishes a GitHub Release (one version string, one wheel). Later merges at the same version do not replace it. The splash (`corvus gui`) is a local display; it does not talk to Node and does not write launch rules.

## What v0.1.8 does not claim

- Four isolated engine processes inside the guest
- Confidential computing against the host
- A networked GUI (the splash is local Qt only)
- Provider API keys in the guest (keys stay on Node when they land)
- A virtio-fs / bind-mount of the host tree into the guest, or more than one `--workspace` path

## Reporting

Email **ops@blackrainlabs.com**. Do not file public issues for unreleased isolation bugs.

**Black Rain Labs - Research & Development Division**
