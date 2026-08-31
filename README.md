# Corvus-Node

**Corvus** is a private AI agent for your Linux PC.

You talk to it in the terminal. It stays in its own locked room — a tiny virtual machine — and cannot wander the rest of your computer. You choose whether it may see a folder. The model never gets a free pass around those rules.

[Black Rain Labs](https://www.BlackRainLabs.com) · **Version 0.1.6** · [AGPLv3](LICENSE)

This preview uses a **practice model** (a stub) so you can try the real isolation path today. A live model comes later.

## Install

64-bit Linux (Intel/AMD or ARM) with virtualization turned on — most PCs already have this.

```bash
git clone https://github.com/BlackRainLabs/Corvus-Node.git
cd Corvus-Node
./install.sh
```

The installer may ask for your password to set up isolation. **Chatting does not use sudo.** The agent never gets your admin account.

Re-run `./install.sh` anytime. Steps that are already done print green **already up to date**. Add `--yes` if you do not want to press Enter.

## First run

```bash
corvus status              # is Corvus up?
corvus vm start            # start the isolated agent
corvus chat                # type a line, then /exit
corvus vm stop             # end the session; Corvus stays ready
```

`corvus` is on your PATH after install. If a command says Corvus is not running, run `./install.sh` again.

### Everyday commands

| Command | What it does |
| --- | --- |
| `corvus status` | Is Corvus up? Is an agent session running? |
| `corvus vm start` | Start the isolated agent (`corvus start` is the same) |
| `corvus chat` | Talk to it until you type `/exit` (the session stays up) |
| `corvus vm stop` | End the agent session; Corvus stays ready in the background (asks first) |
| `corvus stop` | End the session **and** shut Corvus down (asks first) |
| `corvus vm status` | Agent session only |
| `corvus run --once "hello"` | One reply, then done |
| `corvus update` | Install a newer release (stops Corvus first if it is running) |

Optional: `--tools echo` lets the agent echo text back. `--workspace /path --tools file_read` lets it read files in that folder only — nowhere else. `corvus settings` remembers those choices. A running session does not pick up new rules; `vm stop` then `vm start`. Add `--yes` to skip the “are you sure?” prompt on stop or update.

### If something goes wrong

- The installer prints red **need** lines — install what it asks, turn virtualization on in firmware if it says so, run `./install.sh` again.
- `corvus status` shows `Node: down` — Corvus is not running in the background. `./install.sh` (or `sudo systemctl start corvus-node`).
- `Isolation: not ready` — run `./install.sh` again so the agent environment finishes installing.
- `chat` / `vm start` refuse to run if Corvus is down. That is intentional.
- Permission denied — re-run `./install.sh`. After that, `corvus` should just work.

## What this preview includes

Chat, start and stop, an echo tool, and reading or writing files in a folder you allow.

**Not yet:** a live AI model, extra skills, long-term memory, or a graphical app. Commands that are not built yet say so and do nothing.

## How it stays private

You talk to `corvus`. A background service (**Node**) is the only door. The agent itself runs in a small virtual machine and cannot reach the rest of your PC unless you allow a folder. The model cannot call tools on its own.

That is the product: isolation, not a plugin.

## For contributors

Operator copy (this README, `./install.sh`, `corvus --help`) stays plain language. Architecture, isolation rules, and the four-engine model live in the docs below.

- [Contributing](CONTRIBUTING.md) — license, changelog, tests
- [Architecture overview](docs/architecture/OVERVIEW.md) — invariants (authoritative)
- [Agent workflow](docs/architecture/AGENT-WORKFLOW.md) — guest engines
- [Policy](docs/architecture/POLICY.md) — what is allowed
- [Operations](docs/planning/OPERATIONS.md) — bake, smoke, paths
- [Security](SECURITY.md) — threat model
- [Roadmap](docs/planning/ROADMAP.md)
- [Guest image](guest/README.md)
- [Changelog](CHANGES.md)
- [AGENTS.md](AGENTS.md) — layout for this tree

Dev loop (no virtual machine): `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && make test && make lint`

## License

Copyright (C) 2026 Black Rain Labs.

Corvus-Node is free software under the [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later). If you modify it and run it as a network service, AGPL section 13 requires you to offer the corresponding source to those users.

**Black Rain Labs - Research & Development Division**
