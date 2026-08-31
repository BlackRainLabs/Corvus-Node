.DEFAULT_GOAL := help

.PHONY: help check test lint guest-assets install smoke

help:
	@echo "Corvus-Node — install and run (Linux + KVM)"
	@echo
	@echo "  ./install.sh        Guided install into \$HOME/Corvus-Node (sudo when needed)"
	@echo "  make check          Can this machine bake assets and run?"
	@echo "  make guest-assets   Download kernel/VMM and bake the guest disk"
	@echo "  sudo make install   Privileged Node only (after bake; same as installer sudo step)"
	@echo
	@echo "Then (no sudo; installer already entered group corvus):"
	@echo "  corvus status"
	@echo "  corvus vm start"
	@echo "  corvus chat          /exit leaves; VM stays up"
	@echo "  corvus stop          Shut down the guest VM"
	@echo
	@echo "Developers"
	@echo "  make test           Unit tests (no VM)"
	@echo "  make lint"
	@echo "  make smoke          Live KVM against the installed Node"
	@echo
	@echo "Docs: README.md     Contribute: CONTRIBUTING.md"

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
