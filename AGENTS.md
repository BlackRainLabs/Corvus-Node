# AGENTS.md — Instructions for AI Coding Agents

**Project:** Corvus-Node  
**Purpose:** Single-agent harness. **Node** on the host (CLI/GUI, workspaces, RBAC, vsock). Four engines inside one Firecracker VM.

**Product split:** This tree is the agent. Corvus Hypervisor is the later fleet control plane — do not add a supervisor box to this architecture.

## Critical Rules

1. **Start with these documents**:
   - `docs/architecture/OVERVIEW.md` (Core Principles & Invariants — authoritative)
   - `docs/architecture/POLICY.md` (firewall RBAC)
   - Root `SECURITY.md` (threat model)
   - Root `CHANGES.md` (latest changes)
   - `docs/architecture/AGENT-WORKFLOW.md` (guest engine behavior)
   - `docs/planning/OPERATIONS.md` (this-tree vs GitHub release, before-merge loop, bake, smoke)
   - Root `README.md` (operator setup: `./install.sh` into `$HOME/Corvus-Node`)

2. **Implementation code** lives under `src/corvus_node/` (`protocol`, `node` including control/settings/daemon, `runtime`, `policy`, `identity`, `gateway`, `audit`, `llm`, `memory`, `tools`, `vm`). Guest entry is `guest/`.

3. **Changelog is Mandatory**:
   - Every change must be recorded in root `CHANGES.md` with proper format and date.

4. **Per-version runnable CLI**:
   - Each version ships a working operator CLI. `--help` and `status` describe **this build** (what runs, what is not in this version).
   - A verb that is not implemented fails closed with the version id. Never a fake success.
   - `corvus status` runs without KVM and reports isolation gaps plus a GitHub version check.
   - `./install.sh` once (`$HOME/Corvus-Node` venv + group + systemd Node; `corvus` on PATH uses group `corvus` via `sg`). Operator `vm` / `chat` / `run` do not use sudo. `sudo make install` is the inner privileged step.
   - `corvus vm start|stop|status` is the Firecracker guest. `start` is an alias of `vm start`. `vm stop` shuts down the guest only (confirmation; Node stays up). `corvus stop` shuts down the guest then the Node systemd unit (confirmation; sudo for `systemctl stop`).
   - `corvus update` is for the **installed** app vs GitHub **releases** (wheel into `$HOME/Corvus-Node/venv`, not a git clone). It asks to upgrade or keep the current version. If Node is running it then confirms, shuts down the guest and Node, then installs, then starts Node again. `--yes` skips the prompts. It must **not** overwrite a local unreleased tree (dirty, ahead of origin, or version newer than GitHub — the pre-PR internal test case, e.g. local `0.1.6` while GitHub is still `0.1.5`).
   - `./install.sh` from a git checkout (or an unpacked snapshot with `src/`) installs **this tree**. `--release`, or no local source, uses the GitHub release wheel. The installer does not announce a newer GitHub version; `corvus status` / `corvus update` do. Live KVM tests (`make smoke`) need that installed Node. `make test` does not. After clone changes, run `./install.sh` again before smoke. Publish a user build with a `v*` tag (`.github/workflows/release.yml`).

5. **Runtime Agent Workflow**:
   - `AGENT-WORKFLOW.md` is binding for guest behavior.
   - Respect the 4-Engine Model strictly.
   - Engine 3 (LLM) must never directly call tools or memory.
   - Guest-side tools (`echo`) run in the guest after Node RBAC allow. Node never executes arbitrary agent tool code.
   - File I/O on `--workspace` is Node-owned host bytes (like memory). Engine 3 still never opens files.
   - **Stub first:** a new tool or guest-visible LLM behavior is not done until `StubLlm` can exercise it and `make test` covers it. The stub is deterministic (keywords + allowlist), not a provider. Add a case in `tests/test_stub.py`. Live KVM smoke is `make smoke` against the installed Node (`CORVUS_NODE_SMOKE=1`, no sudo).

6. **Documentation Standards**:
   - Update "Last Updated" dates.
   - Maintain Related Documents and "Must Update on Change: CHANGES.md".
   - Avoid `---` YAML frontmatter separators on docs.

7. **Isolation**:
   - Production path is Firecracker + vsock. No TCP product mode.
   - CLI/GUI talk to Node on host AF_UNIX (`0660`, group `corvus`). The Node **service** needs jailer/KVM/root. The operator CLI does not. `vm` / `chat` fail closed if Node is not running (`./install.sh`).
   - Workspace host paths are an allowlist on **Node**. Node reads and writes those files after RBAC. The guest does not mount the host folder.

8. **Do not copy Corvus Hypervisor.** Use it as a principles spec. Do not paste `src/corvus/`, the Operator Console, catalogs, or grants.

See the full workflow rules in `docs/architecture/AGENT-WORKFLOW.md`.

**Black Rain Labs - Research & Development Division**
