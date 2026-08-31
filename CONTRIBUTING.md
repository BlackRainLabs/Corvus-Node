# Contributing

**Organization:** Black Rain Labs
**Division:** Research & Development Division

To **install and run** Corvus-Node as an operator, start with [README.md](README.md) (`make check`, `make guest-assets`, `sudo make install`). This file is for people changing the code.

## Workflow

1. Read `AGENTS.md` and `docs/architecture/OVERVIEW.md` before changing behavior.
2. Keep Engine 3 isolated from tools and memory.
3. Record every change in root `CHANGES.md` (date, documents modified, key changes, reviewed by).
4. Update "Last Updated" on docs you touch. Do not add YAML `---` frontmatter.
5. Run `make test` and `make lint`.
6. **Stub first.** New tools or LLM-facing behavior must be reachable from `StubLlm` (`src/corvus_node/llm/stub.py`) so CI can test the path without a provider. Extend `_pick_calls` (or the keyword lists), add `tests/test_stub.py`, and a paired-turn test when the tool path runs. Do not wait for a real model.

Dev loop (no VM):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
make lint
```

## Isolation

Do not add a TCP or in-process product mode. Tests may pair host and guest over an anonymous socket for unit coverage; that is not a supported run path.

## License

By contributing you agree that your work is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later), the same license as Corvus-Node. See `LICENSE`.

**Black Rain Labs - Research & Development Division**
