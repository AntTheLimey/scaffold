.PHONY: install test lint format typecheck check clean coverage

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/pre-commit install

test:
	.venv/bin/pytest tests/ -v

coverage:
	.venv/bin/pytest tests/ --cov=orchestrator --cov-report=term-missing --cov-fail-under=75

lint:
	.venv/bin/ruff check orchestrator/ tests/

format:
	.venv/bin/ruff format orchestrator/ tests/

typecheck:
	.venv/bin/pyright orchestrator/

check: lint typecheck test

clean:
	rm -rf .pytest_cache __pycache__ *.egg-info dist build htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
