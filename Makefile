PYTHON ?= python3

.PHONY: help install dev lint format test check fixtures clean

help:
	@echo "make dev       install the package in editable mode with dev extras"
	@echo "make lint      run ruff (lint + format check)"
	@echo "make format    auto-format with ruff"
	@echo "make test      run the offline pytest suite"
	@echo "make check     lint + test (what CI runs)"
	@echo "make fixtures  regenerate tests/fixtures from the live calendars"

install:
	$(PYTHON) -m pip install .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

test:
	$(PYTHON) -m pytest

check: lint test

fixtures:
	$(PYTHON) scripts/refresh_fixtures.py

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
