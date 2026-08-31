.DEFAULT_GOAL := help

.PHONY: help check test lint guest-assets install smoke

help:
	@echo "Corvus-Node — a private AI agent for Linux"
	@echo
	@echo "  ./install.sh        Install (password only when needed)"
	@echo
	@echo "Then:"
	@echo "  corvus status       Is Corvus up?"
	@echo "  corvus vm start     Start the isolated agent"
	@echo "  corvus chat         Talk to it; type /exit when done"
	@echo "  corvus vm stop      End the session; Corvus stays ready"
	@echo "  corvus stop         Shut everything down (asks first)"
	@echo
	@echo "Developers — CONTRIBUTING.md"
	@echo "  ./install.sh        This clone into \$HOME/Corvus-Node"
	@echo "  make check          Can this machine install and run?"
	@echo "  make guest-assets   Build the agent disk"
	@echo "  sudo make install   Privileged step (./install.sh does this)"
	@echo "  make test           Unit tests (no virtual machine)"
	@echo "  make lint"
	@echo "  make smoke          Live run against the installed Corvus"
	@echo
	@echo "Ship a version: bump pyproject + __version__ + README, merge main"
	@echo
	@echo "Docs: README.md"

check:
	bash packaging/check-prereqs.sh

test:
	pytest -q

lint:
	ruff check src tests guest
	ruff format --check src tests guest

guest-assets:
	bash guest/bake.sh

install:
	bash packaging/install.sh

smoke:
	CORVUS_NODE_SMOKE=1 pytest tests/test_kvm_smoke.py -q
