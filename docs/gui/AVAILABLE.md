**Document:** AVAILABLE.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** REQUESTS.md (gui/REQUESTS.md), OVERVIEW.md, POLICY.md, CHANGES.md
**Must Update on Change:** CHANGES.md
**AI Instruction:** Core owns this file. When you add a control-socket RPC on Node, document it here. The GUI may only call what this list names.

# Control surface available to the GUI

The operator GUI is a thin client of **Node**, same layer as `corvus`. It talks only over the host **AF_UNIX** control socket (`0660`, group `corvus`). It does not talk to Firecracker, vsock, or guest engines.

v0.1.7 splash (`corvus gui`) does **not** call Node. This list is the contract for later GUI work. A verb that is not here stays fail-closed.

GUI agents must not edit Node, guest, jailer, or RBAC. Ask for a surface in [gui/REQUESTS.md](../../gui/REQUESTS.md). Core ships it here or rejects it.

## Frames (JSON lines)

Each frame is `{"type": "<name>", "payload": { ... }}` plus a newline. Unknown types get `error` with `code: unknown`.

| Client type | When | Reply | Payload in / notes |
| --- | --- | --- | --- |
| `status` | anytime Node is up | `status_ok` | Snapshot: `state` (`idle` / `running`), `pid`, `vm_instance_id`, `tools`, `workspace` |
| `settings_get` | anytime Node is up | `settings_ok` | Active VM tools and workspace if the guest is up; empty lists if idle |
| `start` | Node idle | `start_ok` or `error` | Launch rules: tools, workspace. `error` `busy` if a guest is already running; `boot` if isolation fails |
| `stop` | guest running or idle | `stop_ok` | Ends the guest session. Node stays up (`state: idle`) |
| `shutdown` | anytime Node is up | `shutdown_ok` | Stops the guest then exits the Node process |
| `chat_attach` | guest running | `waiting` or `error` | Exclusive attach. `error` `idle` if no guest; `busy` if chat is already attached |
| `user` | after `chat_attach` | `agent` then `waiting` | `{ "text": "..." }` — one operator turn. `error` `stopped` if the guest ended |
| `stop` (on an attached chat) | attached | `stop_ok` | Ends the guest from the chat connection |

The CLI also writes launch rules via `settings` files on the host (`$XDG_CONFIG_HOME/corvus-node/launch.json`). That is the **firewall console**. The GUI must not write those rules unless the principal is bound to role `operator` (POLICY). The v0.1.7 splash does not write rules.

**Black Rain Labs - Research & Development Division**
