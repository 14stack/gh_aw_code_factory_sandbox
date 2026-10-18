PYTHON ?= python

.PHONY: lint-check test-unit

lint-check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy

test-unit:
	$(PYTHON) -m pytest
