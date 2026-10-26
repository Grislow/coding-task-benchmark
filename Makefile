.PHONY: setup start test

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev,fastapi]"
	@if command -v npm >/dev/null; then npm ci --prefix src/ctb/langs/node --no-audit --no-fund; else echo "npm not found: JavaScript and Express tasks need Node 22 and npm"; fi

start:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	.venv/bin/ctb ui

test:
	@test -x .venv/bin/pytest || { echo "Run make setup first"; exit 1; }
	.venv/bin/pytest
