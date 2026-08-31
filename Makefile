.DEFAULT_GOAL := help

.PHONY: help check test lint guest-assets install smoke git-dates

help:
	@echo "Corvus-Node — a private AI agent for Linux"
	@echo
	@echo "  ./install.sh        Install (password only when needed)"
	@echo
	@echo "Then:"
	@echo "  corvus status       Is Corvus-Node up?"
	@echo "  corvus start        Bring Corvus-Node up (asks before the VM; Enter skips)"
	@echo "  corvus vm start     Start the isolated agent"
	@echo "  corvus chat         Talk to it; type /exit when done"
	@echo "  corvus gui          Splash (this preview)"
	@echo "  corvus vm stop      End the session; Corvus-Node stays ready"
	@echo "  corvus stop         Shut everything down (asks first)"
	@echo
	@echo "Developers — CONTRIBUTING.md"
	@echo "  ./install.sh        This clone into \$HOME/Corvus-Node"
	@echo "  make check          Can this machine install and run?"
	@echo "  make guest-assets   Build the agent disk"
	@echo "  sudo make install   Privileged step (./install.sh does this)"
	@echo "  make test           Unit tests (no virtual machine)"
	@echo "  make lint"
	@echo "  make smoke          Live run against the installed Corvus-Node"
	@echo
	@echo "Ship a version: bump pyproject + __version__ + README, merge main"
	@echo
	@echo "Docs: README.md"

check:
	bash packaging/check-prereqs.sh

git-dates:
	bash packaging/check-git-dates.sh

test: git-dates
	pytest -q

lint: git-dates
	ruff check src tests guest gui
	ruff format --check src tests guest gui

guest-assets:
	bash guest/bake.sh

install:
	bash packaging/install.sh

smoke:
	CORVUS_NODE_SMOKE=1 pytest tests/test_kvm_smoke.py -q
