.PHONY: setup start demo check run test lint

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev,fastapi]"
	git config core.hooksPath .githooks
	@if command -v npm >/dev/null; then npm ci --prefix src/ctb/langs/node --no-audit --no-fund; else echo "npm not found: JavaScript and Express tasks need Node 22 and npm"; fi

start:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	.venv/bin/ctb ui

demo:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	.venv/bin/ctb ui --agents fake --test-author fake --skip-review

check:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	.venv/bin/ctb check

run:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	@test -n "$(TASK)" || { echo "Usage: make run TASK=examples/binary_gap.md"; exit 1; }
	.venv/bin/ctb interview "$(TASK)"

test:
	@test -x .venv/bin/pytest || { echo "Run make setup first"; exit 1; }
	.venv/bin/pytest

lint:
	@test -x .venv/bin/ruff || { echo "Run make setup first"; exit 1; }
	.venv/bin/ruff check src tests
	scripts/check-private.sh
