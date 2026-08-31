.PHONY: test lint guest-assets install smoke

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
