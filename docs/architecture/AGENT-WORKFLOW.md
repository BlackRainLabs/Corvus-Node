**Document:** AGENT-WORKFLOW.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OVERVIEW.md, POLICY.md, OPERATIONS.md, CHANGES.md, SECURITY.md
**Must Update on Change:** CHANGES.md
**AI Instruction:** When revising this document, review Core Principles & Invariants in OVERVIEW.md. Engine 3 must never call tools or memory. Node is on the host; engines are in the VM.

# Agent Workflow Rules

## Purpose

Mandatory rules for the four engines inside the Firecracker VM. Guest code is untrusted. **Node** runs on the host and is the only peer on vsock.

## Core workflow principles

1. **All external actions are mediated** — No direct tool calls, memory access, or host I/O from Engine 3.
2. **Strict engine separation** — Engines do not call each other. They send messages over vsock to Node.
3. **Node is the only host peer** — Every outbound hop is AF_VSOCK to Node. Node validates type, engine, and policy.
4. **Deterministic validation first** — Metadata, correlation, capability tags, hop MAC — never LLM judgment in Node. HMAC does not prove a pwned guest.
5. **Full traceability** — Every action carries a correlation chain back to user intent.
6. **Workspaces belong to Node** — Allowed directories are selected on the host. Node reads and writes those files after RBAC. Engines see `/workspace` paths only; they do not open the host tree.
7. **Default deny** — Chat is implicit. Tools run only after Node allow for this principal. Engine 2 formats replies; the gateway (identity) is on Node.

## Turn lifecycle

| Phase | Description |
|-------|-------------|
| **INIT** | VM boot, vsock handshake with Node |
| **RECEIVE** | Inbound `user_query` from Node |
| **DISPATCH** | Route to the correct engine |
| **COLLECT** | Gather engine results; Engine 1 may run tools only after `tool_call_response.approved` |
| **RESPOND** | Engine 2 sends `agent_response` to Node over vsock |
| **NEXT** | Chat waits for another `user_query` on the same session |
| **DONE** | Node sends `session_end` (`run --once` after one turn, or `corvus vm stop` / `corvus stop`) |
| **ABORTED** | Terminal failure; no further engine work |

`DONE` and `ABORTED` are the only terminal phases. After `vm start`, Node repeats RECEIVE–RESPOND until `vm stop`. `corvus start` brings Node up and asks before the guest (Enter skips the VM). `corvus chat` is a live session with a sticky header; `/exit` detaches and does not send `session_end`. `corvus vm stop` always shuts down the guest first (confirmation); the Node service stays idle. `corvus stop` then stops Node (confirmation; sudo for systemd).

## Engine rules

### Engine 1 — Tools

- May originate `tool_call` and `tool_result` only.
- Must not execute until inbound `tool_call_response` has `approved: true`.
- Guest-side tools (`echo`) run in the guest after allow. Node never runs arbitrary agent tool code.
- `file_read` / `file_write` are Node-owned host I/O on `--workspace`. Engine 1 must use `tool_call_response.result` and must not open host files.
- File-tool paths stay under `/workspace`. Node denies and flags `path_escape` before allow.

### Engine 2 — Channels

- Formats `agent_response` for the user (CLI/GUI via Node).
- Does not identify users or talk to Telegram/WhatsApp. Those adapters sit on Node.

### Engine 3 — LLM (highly restricted)

- Must not call tools, open files, or access memory.
- Must not hold provider API keys (those stay on Node).
- Emits `llm_request` only; waits for `llm_response`.
- When `llm_response` includes `tool_calls`, Engine 3 records them for Engine 1. It does not execute them.
- Node's `StubLlm` is the test stand-in. A new tool is not done until the stub can request it from user text and `make test` covers that path.

### Engine 4 — Memory

- Only engine that may originate `memory:query` / `memory:write`.
- Node owns the store (`private` namespace in v1).

**Black Rain Labs - Research & Development Division**
