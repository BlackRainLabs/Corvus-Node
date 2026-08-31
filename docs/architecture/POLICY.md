**Document:** POLICY.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OVERVIEW.md, AGENT-WORKFLOW.md, OPERATIONS.md, CHANGES.md
**Must Update on Change:** CHANGES.md
**AI Instruction:** When revising this document, review Core Principles & Invariants in OVERVIEW.md. Node performs deterministic RBAC only. No LLM inspection on the host. CLI writes rules; it does not skip the filter.

# Policy — RBAC baked in at the core

v0.1.6. Filter, principal, hop MAC, and default-deny chat live in **Node**. This is not a bolt-on.

## Trust model

The local CLI is the **firewall console**, at the same layer as a later GUI. It writes launch rules (`settings`, `--tools`, `--workspace`). Every turn still hits the filter. `corvus vm start` boots one VM with those rules. `corvus chat` attaches; it does not change the allowlist. `run --once "hello"` is one chat turn then exit. `--workspace` does not imply file tools. Changing tools or workspace requires `vm stop` then `vm start`.

GUI and social channels later are **untrusted interfaces**. They never write rules unless the principal is bound to role `operator`. The gateway lives on Node, not in the guest. Engine 2 only formats `agent_response`. No supervisor box.

**Default deny. Chat is the implicit allow.** Anything else is an added rule or an elevation.

## Evaluation order

First match wins. Implicit last rule: deny.

1. **Wire** — HMAC + seq. Drop and flag on failure. Not an RBAC allow.
2. **Path** — engine may send this message type (`ALLOWED_OUTBOUND`).
3. **Launch capability** — tool must be in the VM allowlist. Adding a tool requires a new microVM.
4. **Workspace** — `file_read` / `file_write` require `--workspace`. The path must stay under `/workspace` after normalize. Else deny and flag `path_escape`. Node then reads or writes the host allowlist (not a guest disk).
5. **Principal rule** — this identity may use that capability. `--tools echo` installs echo in the guest and an allow rule for the **operator** only.
6. **Risk action** — `allow` / `deny` / `elevate` / `flag`.

## Zones and principals

- Zone `console` — local CLI (and later GUI) over the host control socket. Role `operator`. Writes rules.
- Zone `local_gui` — reserved for GUI login later.
- Zone `channel` — social adapters. Default role `user`, chat-only.

Principal: `{issuer, subject, role}` (e.g. `local:operator`, `telegram:12345`). v0.1.2 CLI always uses `local:operator`. Telegram/WhatsApp adapters are stubs.

## Tool tags

Deterministic. No LLM judgment on Node.

- `chat` — implicit, no tool
- `low` — `echo`, `file_read` (operator allow if launched)
- `write` — `file_write`; `elevate` for non-operator
- `exec` / `net` — future shell/network; `elevate` for non-operator

`tools_schema` sent to the LLM is the intersection of the launch allowlist and this principal’s **allow** rules.

## Elevation

Approval of a **call**, not adding a tool mid-VM. Operator + tool in launch list: allow. Non-operator risky tag: `tool_call_response` with `approved: false` and `code: ELEVATE_REQUIRED`. This slice records the event and denies (fail closed). No TTY prompt in `--once`.

## Hop integrity

Host-minted hop key on `session_init` (never on cmdline, never fully logged). Envelope v1.1: `seq`, `payload_sha256`, `mac` (HMAC-SHA256) bound to `vm_instance_id`. Only `session_init` is unsigned bootstrap; later hops must verify. Failure flags `mac_fail` / `replay` / `seq_gap`. Stops mid-path alteration on vsock. Does not prove user intent. Does not authenticate a pwned guest.

`tool_result` must match an outstanding approved `tool_call` id. Unbound results are denied and flagged.

## Flags

Deterministic: `mac_fail`, `engine_spoof`, `unknown_tool`, `deny_burst`, `replay`, `seq_gap`, `unbound_tool_result`, `turn_cap`, `path_escape`. File-tool paths must stay under `/workspace` after normalize. File tools are hidden unless `--workspace` is set.

**Black Rain Labs - Research & Development Division**
