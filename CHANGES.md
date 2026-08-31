# Architecture Changes Log

**Last Updated:** 2026-08-31
**Organization:** Black Rain Labs
**Division:** Research & Development Division

## [2026-08-31] - installer does not fail closed without GUI deps

**Documents Modified:**
- `pyproject.toml`, `packaging/install.sh`, `packaging/operator-install.sh`
- `src/corvus_node/cli.py`, `tests/test_gui.py`, `tests/test_operator_install.py`
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `docs/architecture/OVERVIEW.md`, `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`, `CHANGES.md`

**Key Changes:**
- PySide6 is an optional extra (`gui`). `./install.sh` and `corvus update` still try PySide/Qt, but a miss does not abort: the CLI and Node stay available. `corvus gui` still fail-closes if PySide/Qt is missing.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - splash duration; Releases stay one version, one wheel

**Documents Modified:**
- `gui/corvus_gui/splash.py`, `tests/test_gui.py`
- `src/corvus_node/node/update.py`, `src/corvus_node/cli.py`, `tests/test_update.py`
- `.github/workflows/release.yml`, `.github/workflows/test.yml`
- `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `README.md`, `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`, `CHANGES.md`

**Key Changes:**
- `corvus gui` splash is animated (fade, chrome pulse, scan) and lasts about 8 seconds (`CORVUS_NODE_GUI_MS` still overrides for tests).
- GitHub Releases are immutable: one version string, one wheel. Merge PRs at the current version. Bump (`0.1.8`, …) only when operators should get a new Release. `corvus update` and `./install.sh --release` compare version numbers. Contributors use `./install.sh` from the clone for unreleased `main`.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - v0.1.7 splash GUI; installer ships PySide/Qt

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`
- `gui/corvus_gui/`, `gui/REQUESTS.md`, `gui/README.md`, `docs/gui/AVAILABLE.md`
- `.github/workflows/release.yml`, `packaging/operator-install.sh`, `Makefile`
- `.cursor/rules/gui-team.mdc`, `.cursor/rules/core-no-qt.mdc`, `CODEOWNERS`
- `tests/test_gui.py`, `tests/test_cli.py`, `tests/test_operator_install.py`
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `docs/architecture/OVERVIEW.md`, `docs/architecture/POLICY.md`
- `docs/planning/ROADMAP.md`, `docs/planning/OPERATIONS.md`, `CHANGES.md`

**Key Changes:**
- Version **0.1.7**. `corvus gui` shows a local PySide6 splash (no Node). Fail-closes if PySide/Qt is missing. `./install.sh` installs PySide6 (required wheel dependency) and host xcb/EGL libs. `corvus update` upgrades the same wheel (CLI and GUI).
- Releases ship `gui/corvus_gui/` only. GUI workflow files (`REQUESTS.md`, AVAILABLE.md, Cursor rules) stay in git.
- GUI team owns `gui/`; core owns Node and `docs/gui/AVAILABLE.md`.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - product name is Corvus-Node; corvus is the CLI

**Documents Modified:**
- `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`, `src/corvus_node/node/control.py`
- `packaging/operator-install.sh`, `tests/test_cli.py`, `tests/test_operator_install.py`
- `README.md`, `Makefile`, `AGENTS.md`, `CONTRIBUTING.md`
- `docs/planning/OPERATIONS.md`, `.cursor/rules/branding.mdc`, `CHANGES.md`

**Key Changes:**
- Operator copy and docs call the product **Corvus-Node**. `corvus` is only the CLI command. Never refer to this product as Corvus (a different creator's project). `$HOME/Corvus-Node`, group `corvus`, `corvus-node.service`, and Corvus Hypervisor stay.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - start asks before the VM; Black Rain Labs branding

**Documents Modified:**
- `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`, `src/corvus_node/node/daemon.py`
- `tests/test_cli.py`, `tests/test_strip_ai_trailers.py`
- `packaging/strip-ai-trailers.sh`, `packaging/operator-install.sh`, `packaging/check-prereqs.sh`
- `.githooks/commit-msg`, `.cursor/rules/branding.mdc`, `.cursor/rules/git-timestamps.mdc`
- `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, `Makefile`, `SECURITY.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `docs/architecture/OVERVIEW.md`, `docs/architecture/AGENT-WORKFLOW.md`
- `guest/README.md`, `CHANGES.md`

**Key Changes:**
- `corvus start` is no longer an alias of `vm start`. It brings Node up and asks before starting the guest (Enter skips; `--yes` starts the VM). `vm start` still boots the guest with no extra prompt.
- Commits and docs are **Black Rain Labs - Research & Development Division**. Strip Cursor / AI trailers (`Co-authored-by: Cursor`, Made by, Created by). Human GitHub Contributors are allowed.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - commits and Releases use the wall clock

**Documents Modified:**
- `packaging/check-git-dates.sh`, `tests/test_check_git_dates.py`, `Makefile`
- `.github/workflows/release.yml`, `.cursor/rules/git-timestamps.mdc`
- `AGENTS.md`, `CONTRIBUTING.md`, `docs/planning/OPERATIONS.md`, `CHANGES.md`

**Key Changes:**
- Never export `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`. `make test` refuses them. Release CI unsets those variables and `SOURCE_DATE_EPOCH` so wheels and GitHub Releases are stamped now. GitHub lists files by author date.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - every new version is a GitHub Release

**Documents Modified:**
- `.github/workflows/release.yml`, `tests/test_cli.py`
- `CONTRIBUTING.md`, `AGENTS.md`, `README.md`, `Makefile`, `SECURITY.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`, `CHANGES.md`

**Key Changes:**
- Deploy: bump `pyproject.toml`, `__version__`, and README, merge to `main`. CI publishes `vX.Y.Z` (wheel + install tarball) if that version has no Release yet. A manual `v*` tag still works. Doc-only merges on an already-released version do not cut a new Release.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - README leads with the user install tarball

**Documents Modified:**
- `README.md`, `packaging/operator-install.sh`, `.github/workflows/release.yml`
- `docs/planning/OPERATIONS.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CHANGES.md`

**Key Changes:**
- README **Install** is the GitHub Release bundle (`corvus-node-install.tar.gz`), not a clone. Clone stays under **For contributors**. Releases also attach a stable `corvus-node-install.tar.gz` name so `/releases/latest/download/` works.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - workflow docs match clone vs GitHub release

**Documents Modified:**
- `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, `Makefile`, `CHANGES.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `docs/architecture/OVERVIEW.md`, `guest/README.md`

**Key Changes:**
- Docs state the same loop: `make test` is the clone `.venv`; `./install.sh` from this tree updates `$HOME/Corvus-Node`; `make smoke` hits that Node. `corvus update` / `--release` are GitHub. The installer does not announce a newer GitHub version. `sg` is how group `corvus` is regained (no `newgrp` at install end).

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - local git vs GitHub release; upgrade or keep

**Documents Modified:**
- `packaging/operator-install.sh`, `packaging/install.sh`
- `src/corvus_node/node/update.py`, `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`
- `.github/workflows/release.yml`
- `tests/test_update.py`, `tests/test_cli.py`, `tests/test_operator_install.py`
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`, `CHANGES.md`

**Key Changes:**
- `./install.sh` from a git checkout (or an unpacked snapshot) installs **this tree**. `--release` (or no local source) fetches the GitHub **release wheel**. If Corvus is already installed, the installer asks to **upgrade** or **keep** the current version before stopping Node.
- `corvus update` pip-installs that wheel (not `git+https`), asks the same upgrade-or-keep question, then bounces Node if it is up. A `v*` tag builds the wheel and a slim install tarball (no tests/docs) onto a GitHub Release.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - status does not call empty GitHub tags “unreachable”

**Documents Modified:**
- `src/corvus_node/node/update.py`, `tests/test_update.py`
- `docs/planning/OPERATIONS.md`, `CHANGES.md`

**Key Changes:**
- `corvus status` talks to GitHub’s tags API. This repo has no tags yet, so the check used to print **GitHub unreachable**. It now says **no GitHub tags yet** when the API answers with an empty list. Skip vs network failure stay distinct. Tests accept **version check skipped** when `CORVUS_NODE_SKIP_UPDATE_CHECK=1` (CI is a clean checkout).

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - status is scannable; installer prints a brief block

**Documents Modified:**
- `src/corvus_node/cli.py`, `packaging/operator-install.sh`
- `tests/test_cli.py`, `tests/test_operator_install.py`
- `docs/planning/OPERATIONS.md`, `CHANGES.md`

**Key Changes:**
- `corvus status` leads with Node/VM, then blank-line groups for this preview, version, and isolation. `--brief` is Node and VM only.
- `./install.sh` prints a **Status** section (brief, colored) before **You're set**, instead of dumping the full status wall into the install log.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - jailer kernel EACCES; reinstall when source is newer

**Documents Modified:**
- `src/corvus_node/vm/launcher.py`, `packaging/operator-install.sh`
- `tests/test_launcher.py`, `tests/test_operator_install.py`
- `docs/planning/OPERATIONS.md`, `CHANGES.md`

**Key Changes:**
- Jailer drops to an unprivileged uid before Firecracker opens `/vmlinux`. The jail copy of the kernel and rootfs is now a real copy (not a hardlink) owned by that uid, so boot is not Permission denied.
- `./install.sh` reinstalls when this checkout is newer than the installed package (same version string is not enough). After start, it waits for Corvus to come up before printing status.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - operator copy in plain language

**Documents Modified:**
- `README.md`, `CONTRIBUTING.md`, `Makefile`, `CHANGES.md`
- `packaging/operator-install.sh`, `packaging/install.sh`
- `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`, `src/corvus_node/node/control.py`, `src/corvus_node/node/chatview.py`
- `tests/test_cli.py`, `tests/test_operator_install.py`, `tests/test_chatview.py`

**Key Changes:**
- README, `./install.sh`, `corvus --help`, and stop/update confirmations talk to a first-time user (private agent, locked room, password only for isolation). Firecracker, jailer, Engine 3, vsock, and systemd stay in contributor docs.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - install and update stop a running Node (confirm)

**Documents Modified:**
- `packaging/operator-install.sh`, `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`
- `tests/test_cli.py`, `tests/test_operator_install.py`
- `README.md`, `AGENTS.md`, `SECURITY.md`, `CHANGES.md`
- `docs/planning/OPERATIONS.md`

**Key Changes:**
- `./install.sh` detects a live Node (systemd or control socket), explains that replacing files under a running process is unsafe, and asks before shutting down the guest and Node. `--yes` confirms. Install then starts Node again.
- `corvus update` does the same: confirm, stop guest + Node, pip the GitHub tag, start Node. `--yes` skips the prompt. Unreleased local trees still refuse to install from GitHub.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - corvus stop is full shutdown; vm stop is guest-only

**Documents Modified:**
- `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`, `src/corvus_node/node/daemon.py`
- `tests/test_cli.py`, `tests/conftest.py`, `tests/test_kvm_smoke.py`
- `README.md`, `AGENTS.md`, `SECURITY.md`, `CHANGES.md`, `Makefile`
- `docs/architecture/OVERVIEW.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `ROADMAP.md`
- `packaging/operator-install.sh`

**Key Changes:**
- `corvus vm stop` shuts down the Firecracker guest only. It explains that and asks for confirmation (`--yes` skips). Node stays up.
- `corvus stop` is no longer an alias. It shuts down the guest, then the Node systemd unit, explains both, and asks first. Sudo is only for `systemctl stop` (root jailer daemon). `start` remains an alias of `vm start`.
- SIGTERM on the Node serve process (systemd stop) reaps the guest instead of dropping the jailer.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - v0.1.6 guided installer into $HOME/Corvus-Node

**Documents Modified:**
- `install.sh`, `packaging/operator-install.sh`, `packaging/install.sh`, `packaging/check-prereqs.sh`, `packaging/corvus-node.service.in`
- `Makefile`, `pyproject.toml`, `src/corvus_node/__init__.py`, `cli.py`, `node/control.py`, `node/info.py`, `node/settings.py`
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGES.md`
- `docs/planning/OPERATIONS.md`, `ROADMAP.md`, `docs/architecture/OVERVIEW.md`, `POLICY.md`, `guest/README.md`, `guest/bake.sh`
- `tests/test_operator_install.py`, `test_control.py`, `test_chatview.py`, `test_update.py`, `test_kvm_smoke.py`

**Key Changes:**
- Version **0.1.6**. `./install.sh` is the operator path: branded, idempotent, explains sudo, installs missing packages, bakes assets, installs Node under `$HOME/Corvus-Node` (`root:corvus` venv). Jailer chroots stay `/var/lib/corvus-node`. `corvus` is on PATH (`/usr/local/bin`); it uses group `corvus` automatically (no `newgrp`).
- Re-runs skip green already-up-to-date steps. `--yes` and `CORVUS_NODE_INSTALL_DRY=1` for non-interactive / tests. `sudo make install` remains the inner privileged script. `corvus` is installed to `/usr/local/bin` and uses `sg` so a fresh terminal finds the command without `newgrp`. The Node pid file is `root:corvus` so `status` can see a live service.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - README lede: security-first harness

**Documents Modified:**
- `README.md`, `CHANGES.md`

**Key Changes:**
- README opens on Corvus as a security-first AI agent harness (Firecracker guest, Node as the only door, default-deny). Install path and version (0.1.5) unchanged.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - Operator first-run docs and host check

**Documents Modified:**
- `README.md`, `CONTRIBUTING.md`, `CHANGES.md`, `AGENTS.md`
- `Makefile`, `docs/planning/OPERATIONS.md`, `guest/README.md`, `guest/bake.sh`
- `packaging/install.sh`, `packaging/check-prereqs.sh`
- `src/corvus_node/node/info.py`
- `tests/test_check_prereqs.py`

**Key Changes:**
- README leads with clone → check → bake → install → `vm start` / `chat` / `stop` for an operator. Architecture, reference docs, and contribute sit below. Version stays 0.1.5.
- `make check` (`packaging/check-prereqs.sh`) reports KVM, Python 3.12, bake tools, and next steps. Bare `make` prints the same operator cheat sheet. Install and bake print what to run next; missing guest assets are called out instead of a silent incomplete install.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - AGPLv3; stay on v0.1.5

**Documents Modified:**
- `LICENSE`, `pyproject.toml`, `README.md`, `CONTRIBUTING.md`, `CHANGES.md`
- `src/corvus_node/__init__.py`

**Key Changes:**
- This tree is GNU AGPL v3 or later. Apache-2.0 is withdrawn for this codebase. Version stays **0.1.5** (not 0.1.6) until that release is merged.
- Git history that shipped under Apache-2.0 is kept only on a local backup branch (`apache-2-history`) so a replace of `main` can publish an AGPL-only root.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - CLI command is corvus; stop shuts down the VM first

**Documents Modified:**
- `pyproject.toml`, `packaging/install.sh`
- `src/corvus_node/cli.py`, `info.py`, `chatview.py`, `daemon.py`, `update.py`
- `tests/test_cli.py`, `tests/test_kvm_smoke.py`
- `AGENTS.md`, `README.md`, `SECURITY.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`

**Key Changes:**
- The operator command is `corvus` (`/usr/local/bin/corvus`). `corvus-node` remains a symlink/alias. Product name, Python package, systemd unit, and `/opt/corvus-node` are unchanged.
- `corvus stop` and `corvus vm stop` always shut down the Firecracker guest first (`session_end`, then reap). They do not stop the Node systemd service.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - VM verbs + smoke against installed Node

**Documents Modified:**
- `src/corvus_node/cli.py`, `src/corvus_node/node/info.py`, `src/corvus_node/node/daemon.py`
- `tests/test_cli.py`, `tests/test_kvm_smoke.py`
- `Makefile`, `AGENTS.md`, `README.md`, `SECURITY.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`

**Key Changes:**
- `corvus-node vm start|stop|status` controls the Firecracker guest. The Node **service** is systemd (`sudo make install`); it stays up. `start` / `stop` remain aliases of `vm start` / `vm stop`.
- `status` prints Node (up/down) and VM (idle/running) as separate lines so a live Node with no guest is not mistaken for a stopped product.
- KVM smoke (`make smoke` / `CORVUS_NODE_SMOKE=1`) talks to the installed Node with no sudo and no spawned `serve`. `make test` still skips those cases. Skip if Node is down or a guest is already running.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - Live chat until /exit

**Documents Modified:**
- `src/corvus_node/node/chatview.py`, `cli.py`, `daemon.py`, `info.py`
- `tests/test_chatview.py`, `test_cli.py`, `test_control.py`, `test_kvm_smoke.py`, `conftest.py`
- `CHANGES.md`, `README.md`, `SECURITY.md`
- `docs/architecture/AGENT-WORKFLOW.md`, `docs/planning/OPERATIONS.md`

**Key Changes:**
- `corvus-node chat` is a continuous live session, not a one-shot send/receive prompt. `/exit` (or `/quit`) leaves; the guest VM stays up until `stop`.
- A sticky header shows version, model, context (placeholder `—` until token accounting exists), tools/workspace, and how to leave. On a TTY it sits in the alt screen above a scroll region so conversation moves under it.
- Operator control frames for a turn are `user` / `agent` (not `chat_send` / `chat_recv`).

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-31] - v0.1.5 Operator CLI (install once, no sudo to run)

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `AGENTS.md`, `README.md`, `CHANGES.md`, `SECURITY.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `ROADMAP.md`
- `guest/README.md`
- `packaging/`, `Makefile`
- `src/corvus_node/cli.py`, `src/corvus_node/__main__.py`
- `src/corvus_node/node/control.py`, `daemon.py`, `settings.py`, `info.py`, `update.py`
- `src/corvus_node/vm/launcher.py`
- `tests/`

**Key Changes:**
- v0.1.5 is the operator CLI: `start`, `chat`, `stop`, `status`, `settings`, `run --once`, `update`. CLI/GUI talk to Node on host AF_UNIX (`0660`, group `corvus`), not vsock.
- `sudo make install` once: `corvus` group, venv at `/opt/corvus-node`, `/usr/local/bin/corvus-node`, systemd Node daemon, `/etc/corvus-node/env`. After that the operator CLI does not use sudo. `serve` stays root (jailer). `stop` ends the guest VM; the Node service stays idle.
- `corvus-node update` / `status` version check compare `__version__` to GitHub tags and `pip` into the installed prefix. A local unreleased tree (dirty, ahead of origin, or version newer than GitHub — e.g. internal `0.1.5` before the PR merges) does **not** offer an update. Source checkouts are not overwritten; use git for those.
- `run --once` stays an in-process one-shot when the service is down and euid is 0 (KVM smoke). Otherwise it uses the Node service.
- Launch-time immutability unchanged. Settings file + flags still write rules; the filter still runs.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - Chat REPL owns the TTY

**Documents Modified:**
- `CHANGES.md`, `README.md`, `docs/planning/OPERATIONS.md`
- `src/corvus_node/cli.py`, `src/corvus_node/node/session.py`, `src/corvus_node/vm/launcher.py`
- `tests/test_cli.py`

**Key Changes:**
- Jailer/Firecracker no longer inherit the operator TTY. Guest `ttyS0` goes to `serial.log` in the jail; stdin is `/dev/null`.
- `corvus-node chat` prints a banner and `>` on stderr when Node is waiting. An empty stdin prints `stdin closed` instead of exiting silently.
- Interactive chat was exiting right after guest boot because Firecracker serial stole stdin (EOF after handshake) and kernel dmesg hid that there was no REPL.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - v0.1.5 Multi-turn chat

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `README.md`, `CHANGES.md`, `SECURITY.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`
- `src/corvus_node/cli.py`, `src/corvus_node/node/session.py`, `src/corvus_node/llm/stub.py`
- `src/corvus_node/runtime/turn.py`, `src/corvus_node/vm/launcher.py`
- `tests/`

**Key Changes:**
- `corvus-node chat` keeps one jailed VM and the same `--workspace` across prompts. Stub still drives. `.quit` / EOF ends the session (`session_end`).
- `run --once TEXT` is still one turn, then `session_end` and VM teardown.
- Guest loops on `user_query` with a capped in-guest history. Per-turn timeout; session turn cap. No new tools, no Engine 4 store, no provider.
- Stub only treats tool messages after the latest user line as this turn (so a second chat prompt can still pick a tool).
- Next after this slice: more tools. Refresh guest payload after the runtime change.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - Roadmap: stub covers functions; provider after core

**Documents Modified:**
- `docs/planning/ROADMAP.md`, `CHANGES.md`

**Key Changes:**
- Next work is core (Engine 4 memory, then `corvus-node chat`) with `StubLlm` as the test LLM.
- A real provider waits until those components are solid, then one live chat-turn test.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - v0.1.4 Live host workspace

**Documents Modified:**
- `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `README.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`, `guest/bake.sh`
- `src/corvus_node/node/workspace.py`, `src/corvus_node/vm/launcher.py`
- `src/corvus_node/node/session.py`, `src/corvus_node/policy/engine.py`
- `src/corvus_node/runtime/engines.py`, `src/corvus_node/cli.py`
- `tests/`

**Key Changes:**
- `--workspace` is a live host directory Node reads and writes after RBAC (one path). No prepared ext4, no `/dev/vdb`, no copy-out.
- File tools require `--workspace` or they are hidden. Paths stay under `/workspace`; Node flags `path_escape` and refuses symlinks.
- Node returns `file_read` / `file_write` results on `tool_call_response`. Engine 1 uses that result. Echo still runs in the guest.
- Writes land on the host immediately. A later turn, or the user's editor, sees the same files.
- Guest images that still run file tools locally need a payload refresh (`CORVUS_NODE_REFRESH_PAYLOAD=1 make guest-assets`).
- Stub LLM is still deterministic: `edit`/`review` plus a filename pick `file_write`/`file_read`. Stub-first workflow unchanged. `make test` stays VM-free.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - v0.1.4 Prepared workspace disk (superseded)

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `AGENTS.md`, `SECURITY.md`
- `README.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/init.sh`, `guest/README.md`
- `src/corvus_node/vm/workspace.py`, `src/corvus_node/vm/launcher.py`
- `src/corvus_node/tools/`, `src/corvus_node/policy/engine.py`
- `src/corvus_node/runtime/`, `src/corvus_node/llm/stub.py`, `src/corvus_node/cli.py`
- `tests/`

**Key Changes:**
- First cut snapshotted `--workspace` onto a second ext4 with post-turn copy-out. Replaced the same day by live Node I/O (entry above).
- Engine 1 `file_read` / `file_write` path checks and stub-first workflow landed here.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-30] - v0.1.3 Security Checkup (The human objection AI reviewed)

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `AGENTS.md`, `SECURITY.md`
- `README.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `POLICY.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/bake.sh`, `guest/init.sh`, `guest/README.md`
- `src/corvus_node/vm/`, `src/corvus_node/node/session.py`, `src/corvus_node/protocol/mac.py`
- `src/corvus_node/runtime/`, `src/corvus_node/audit/store.py`, `src/corvus_node/cli.py`
- `.github/workflows/test.yml`, `tests/`

**Key Changes:**
- Jailer is the only launch path. Fail closed without root, jailer, KVM, or SHA-256-matching kernel/rootfs/Firecracker/jailer. No raw Firecracker.
- Slim guest payload (protocol/runtime/tools only). PID 1 drops to uid 1000 after mounts. No pip in the image.
- Host-minted hop key on `session_init` (not `handshake_ok`). MAC binds `vm_instance_id`. Turn caps. `tool_result` must match an approved call.
- Durable hash-chained JSONL audit under `XDG_STATE_HOME`. Jail chroot-base is `/var/lib/corvus-node` (not `/run`: that mount is `nodev`, so jailer's `/dev/kvm` cannot be opened). Vsock UDS stays under `sockaddr_un`.
- Jailer `--new-pid-ns` parent exits 0 after clone; Node waits on `firecracker.pid`. Config, `fc.log`, and the vsock UDS are owned by the jailer uid.
- CI: `make test` + `make lint` with SHA-pinned Actions. `make test` stays VM-free.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-28] - v0.1.2 RBAC baked in at the core

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `AGENTS.md`
- `README.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `docs/architecture/POLICY.md`, `docs/architecture/AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`
- `src/corvus_node/identity/`, `src/corvus_node/gateway/`, `src/corvus_node/protocol/`, `src/corvus_node/policy/`
- `src/corvus_node/node/session.py`, `src/corvus_node/runtime/`, `src/corvus_node/cli.py`, `src/corvus_node/audit/`
- `tests/`

**Key Changes:**
- Firewall RBAC on Node: default deny, chat implicit, CLI is the console that writes rules, not a bypass.
- Principals + LocalCliAdapter; Telegram/WhatsApp stubs. `--tools echo` is an operator allow rule only.
- Envelope v1.1 hop HMAC (seq, payload hash, MAC). Handshake bootstraps the session key.
- Elevate/flag audit events. `tools_schema` is principal-scoped. Fail closed on MAC failure.
- Existing v0.1.1 guest rootfs must be rebaked for a live Firecracker turn (Envelope 1.1). `make test` stays VM-free.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-28] - v0.1.1 first real turn

**Documents Modified:**
- `pyproject.toml`, `src/corvus_node/__init__.py`, `Makefile`, `.gitignore`
- `README.md`, `CHANGES.md`
- `docs/architecture/OVERVIEW.md`, `docs/planning/OPERATIONS.md`, `docs/planning/ROADMAP.md`
- `guest/README.md`, `guest/bake.sh`, `guest/init.sh`
- `src/corvus_node/cli.py`, `src/corvus_node/vm/launcher.py`, `src/corvus_node/vm/__init__.py`
- `src/corvus_node/node/session.py`, `src/corvus_node/runtime/turn.py`
- `tests/`

**Key Changes:**
- `corvus-node run --once` boots Firecracker, listens on vsock UDS `{uds}_{4040}`, and completes the stub-LLM / optional echo turn. No TCP fallback.
- `make guest-assets` fetches a pinned Firecracker **v1.16.1** binary plus kernel and Debian bookworm ext4. `corvus-node` resolves `.cache/corvus-node/firecracker` when PATH has no VMM.
- Firecracker logger is attached at launch; boot failures include `fc.log`. KVM smoke stays opt-in (`CORVUS_NODE_SMOKE=1`) so `make test` remains VM-free.
- Launch-time tools travel on `handshake_ok` from Node; they are not baked into the image.
- `--once` is a flag and the user text is positional, so `run --once --tools echo hello` parses. `--workspace` is accepted but not mounted.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-27] - README: drop Hypervisor wording

**Documents Modified:**
- `README.md`, `CHANGES.md`

**Key Changes:**
- Root README describes Corvus-Node on its own. No Corvus Hypervisor references.

**Reviewed By:** Black Rain Labs - R&D

---

## [2026-08-27] - Bootstrap v0.1.0

**Documents Modified:**
- `AGENTS.md`, `README.md`, `CHANGES.md`, `CONTRIBUTING.md`, `LICENSE`, `pyproject.toml`, `Makefile`, `.gitignore`
- `docs/architecture/OVERVIEW.md`, `AGENT-WORKFLOW.md`
- `docs/planning/OPERATIONS.md`, `ROADMAP.md`
- `src/corvus_node/` (protocol, node, runtime, policy, audit, llm, memory, tools, vm, cli)
- `guest/run_guest.py`, `guest/README.md`
- `tests/`

**Key Changes:**
- New repository. Authoritative graph: CLI/GUI → Node → allowed workspaces; Node → AF_VSOCK → Firecracker VM (E1–E4).
- Node is the host product (policy, audit, LLM keys, memory store, workspace allowlist, Firecracker, vsock). Engines live only in the guest. No supervisor component.
- Vertical slice: `user_query` → Engine 3 (stub LLM) → optional Engine 1 `echo` after Node allow → Engine 2 response. CLI without KVM/vsock fails closed. Unit tests do not boot a VM.

**Reviewed By:** Black Rain Labs - R&D

**Black Rain Labs - Research & Development Division**
