# Contributing

**Organization:** Black Rain Labs
**Division:** Research & Development Division

To **install and run** Corvus without this repo, start with [README.md](README.md) (GitHub Release tarball). This file is for people changing the code. `./install.sh` from this clone installs **this tree**. Users of an installed app use `corvus update` (GitHub release wheel).

Operator-facing copy (README, `./install.sh`, `corvus --help`) stays plain language. Isolation rules, Firecracker/jailer, and the four-engine model live in `docs/architecture/`.

## Workflow

1. Read `AGENTS.md` and `docs/architecture/OVERVIEW.md` before changing behavior.
2. Keep Engine 3 isolated from tools and memory.
3. Record every change in root `CHANGES.md` (date, documents modified, key changes, reviewed by).
4. Update "Last Updated" on docs you touch. Do not add YAML `---` frontmatter.
5. Run `make test` and `make lint` (developer `.venv`; not the installed Node).
6. **Stub first.** New tools or LLM-facing behavior must be reachable from `StubLlm` (`src/corvus_node/llm/stub.py`) so CI can test the path without a provider. Extend `_pick_calls` (or the keyword lists), add `tests/test_stub.py`, and a paired-turn test when the tool path runs. Do not wait for a real model.
7. Put **this tree** on the machine with `./install.sh` from the clone (upgrade if Corvus is already installed). Then `make smoke` if you need the live guest. Do not use `corvus update` for that.
8. Open a PR. **Every new version is a GitHub Release.** Bump `pyproject.toml`, `src/corvus_node/__init__.py`, and the README version line together. After merge to `main`, `.github/workflows/release.yml` tags `vX.Y.Z` and publishes the wheel + `corvus-node-install.tar.gz` if that version has no release yet. A manual `git tag vX.Y.Z && git push origin vX.Y.Z` does the same. Do not ship a new version string without that Release.

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
