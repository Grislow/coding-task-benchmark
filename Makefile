.PHONY: setup start test

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev,fastapi]"

start:
	@test -x .venv/bin/ctb || { echo "Run make setup first"; exit 1; }
	.venv/bin/ctb ui

test:
	@test -x .venv/bin/pytest || { echo "Run make setup first"; exit 1; }
	.venv/bin/pytest
