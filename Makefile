.PHONY: install lint format typecheck test check verify clean

# Every change must pass `make check`. Keep these targets
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

verify:
	uv run --frozen python -c 'import secrets, sys, pytest; \
		seed = secrets.randbits(64); \
		print(f"Hypothesis seed: {seed}", flush=True); \
		sys.exit(pytest.main(["tests/property", "--no-cov", "-x", \
		"--hypothesis-profile=demo-deep", f"--hypothesis-seed={seed}", \
		"--hypothesis-show-statistics"]))'

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis htmlcov
	rm -f .coverage coverage.xml
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -not -path "./.venv/*" -exec rm -rf {} +
