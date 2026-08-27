.PHONY: install lint format typecheck test check clean

# Every later task runs `make check` and trusts its output. Keep these targets
# honest: no target may pass by skipping work or by lowering a threshold.

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint typecheck test

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis htmlcov
	rm -f .coverage coverage.xml
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -not -path "./.venv/*" -exec rm -rf {} +
