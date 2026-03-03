# Justfile for UATAQ

# Show available commands
list:
    @just --list

# Build HTML documentation using Sphinx
build-docs:
	@echo "Building HTML documentation..."
	rm -rf docs/_build/
	uv run sphinx-build -M html docs docs/_build

# Clean up build artifacts and cache files
clean:
	@echo "Cleaning up generated files..."
	rm -rf build/
	rm -rf dist/
	rm -rf src/*.egg-info
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf junit.xml
	rm -rf docs/_build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete

# Run pre-commit hooks on all files
pre-commit:
	@echo "Running pre-commit on all files..."
	uv run pre-commit run --all-files

# Run linting, type checking, and tests
quality-check:
	@echo "Running quality checks..."
	@echo "Linting with ruff..."
	uv run ruff check src/uataq
	@echo "Type checking with pyright..."
	uv run pyright src/uataq
	just test

# Run ruff fixes and formatting
ruff:
	@echo "Running ruff fixes and formatting..."
	uv run ruff check --fix src/uataq
	uv run ruff format src/uataq

# Run tests with pytest
test:
	@echo "Running tests..."
	uv run pytest -v
