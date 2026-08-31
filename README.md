# Corvus-Node

**Corvus-Node** is a private AI agent for your Linux PC. The operator command is `corvus` — that is a short name for the CLI, not the product.

You talk to it in the terminal. It stays in its own locked room — a tiny virtual machine — and cannot wander the rest of your computer. You choose whether it may see a folder. The model never gets a free pass around those rules.

[Black Rain Labs](https://www.BlackRainLabs.com) · **Version 0.1.9** · [AGPLv3](LICENSE)

This preview uses a **practice model** (a stub) so you can try the real isolation path today. A live model comes later.

## Install

64-bit Linux (Intel/AMD or ARM) with virtualization turned on — most PCs already have this.

You do **not** need to clone this repository. Download the small install bundle from the [latest GitHub Release](https://github.com/BlackRainLabs/Corvus-Node/releases/latest) (`corvus-node-install.tar.gz` — not the Source code zip).

```bash
curl -fL -o corvus-node-install.tar.gz \
  https://github.com/BlackRainLabs/Corvus-Node/releases/latest/download/corvus-node-install.tar.gz
mkdir -p corvus-install
tar -xzf corvus-node-install.tar.gz -C corvus-install
cd corvus-install
./install.sh
```

If that download fails, there is no GitHub Release yet. Wait for one, or see [For contributors](#for-contributors) to install from a clone.

The installer may ask for your password to set up isolation. **Chatting does not use sudo.** The agent never gets your admin account.

The installer tries to set up the GUI runtime (PySide/Qt). If that is not available, the `corvus` CLI still works. Later, `corvus update` installs a newer GitHub release for the CLI (and GUI extras when they install). Re-run `./install.sh` from the folder you unpacked if you still have it — including if `corvus gui` says Qt libraries are missing. If Corvus-Node is already installed, you can **upgrade** or **keep** the current version. Steps that are already done print green **already up to date**. Add `--yes` if you do not want to press Enter.

## First run

```bash
corvus status              # is Corvus-Node up?
corvus start               # bring Corvus-Node up; asks before the VM (Enter skips)
corvus vm start            # start the isolated agent
corvus chat                # type a line, then /exit
corvus gui                 # splash (this preview)
corvus vm stop             # end the session; Corvus-Node stays ready
```

`corvus` is on your PATH after install. If a command says Corvus-Node is not running, `corvus start`, or `sudo systemctl start corvus-node`, or run `./install.sh` from the folder you unpacked.

### Everyday commands

| Command | What it does |
| --- | --- |
| `corvus status` | Is Corvus-Node up? Is an agent session running? |
| `corvus start` | Start Corvus-Node. Asks before starting the VM; Enter skips. `--yes` starts the VM too |
| `corvus vm start` | Start the isolated agent |
| `corvus chat` | Talk to it until you type `/exit` (the session stays up) |
| `corvus gui` | Splash screen for this preview (checks PySide/Qt; does not talk to the agent) |
| `corvus vm stop` | End the agent session; Corvus-Node stays ready in the background (asks first) |
| `corvus stop` | End the session **and** shut Corvus-Node down (asks first) |
| `corvus vm status` | Agent session only |
| `corvus run --once "hello"` | One reply, then done |
| `corvus update` | Install a newer GitHub release for the CLI and GUI (asks before replacing; stops Corvus-Node first if it is running) |

Optional: `--tools echo` lets the agent echo text back. `--workspace /path --tools file_read` lets it read files in that folder only — nowhere else. `corvus settings` remembers those choices. A running session does not pick up new rules; `vm stop` then `vm start`. Add `--yes` to skip the “are you sure?” prompt on stop or update.

### If something goes wrong

- The installer prints red **need** lines — install what it asks, turn virtualization on in firmware if it says so, run `./install.sh` again.
- `corvus status` shows `Node: down` — Corvus-Node is not running in the background. `corvus start` (or `sudo systemctl start corvus-node`). You do not need to re-run `./install.sh` after `corvus stop`.
- `Isolation: not ready` — run `./install.sh` again so the agent environment finishes installing.
- `chat` / `vm start` refuse to run if Corvus-Node is down. That is intentional. `corvus start` brings Corvus-Node up and asks before the VM.
- Permission denied — re-run `./install.sh`. After that, `corvus` should just work.

## What this preview includes

Chat, start and stop, an echo tool, reading or writing files in a folder you allow, and a splash GUI (`corvus gui`).

**Not yet:** a live AI model, extra skills, long-term memory, or a full operator window. Commands that are not built yet say so and do nothing. If `corvus gui` cannot find PySide/Qt, it says so — run `./install.sh` or `corvus update`.

## How it stays private

You talk to `corvus`. A background service (**Node**) is the only door. The agent itself runs in a small virtual machine and cannot reach the rest of your PC unless you allow a folder. The model cannot call tools on its own.

That is the product: isolation, not a plugin.

## For contributors

Clone this repo only if you are changing the code. `./install.sh` from the clone installs **this tree** (not the GitHub wheel). After you change the clone, run `./install.sh` again, then `make smoke` if you need the live guest. Do not use `corvus update` for that. Bump `pyproject.toml`, `__version__`, and this README only when you want operators to get a new GitHub Release.

```bash
git clone https://github.com/BlackRainLabs/Corvus-Node.git
cd Corvus-Node
./install.sh
```

`--release` fetches the GitHub wheel even from a clone. The installer does not look up GitHub unless you pass `--release`. `corvus status` and `corvus update` do.

Operator copy (this README, `./install.sh`, `corvus --help`) stays plain language. Architecture, isolation rules, and the four-engine model live in the docs below.

- [Contributing](CONTRIBUTING.md) — license, changelog, tests, this-tree install before smoke
- [Architecture overview](docs/architecture/OVERVIEW.md) — invariants (authoritative)
- [Agent workflow](docs/architecture/AGENT-WORKFLOW.md) — guest engines
- [GUI surface](docs/gui/AVAILABLE.md) — control-socket RPCs the GUI may use
- [Policy](docs/architecture/POLICY.md) — what is allowed
- [Operations](docs/planning/OPERATIONS.md) — bake, smoke, paths
- [Security](SECURITY.md) — threat model
- [Roadmap](docs/planning/ROADMAP.md)
- [Guest image](guest/README.md)
- [Changelog](CHANGES.md)
- [AGENTS.md](AGENTS.md) — layout for this tree

Dev loop (no virtual machine): `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && make test && make lint`. Live path: [Operations](docs/planning/OPERATIONS.md).

## License

Copyright (C) 2026 Black Rain Labs.

Corvus-Node is free software under the [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later). If you modify it and run it as a network service, AGPL section 13 requires you to offer the corresponding source to those users.

**Black Rain Labs - Research & Development Division**
