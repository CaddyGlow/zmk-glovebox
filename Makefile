.PHONY: test lint format fmt coverage setup clean docs docs-clean docs-live help

help:
	@echo "Available commands:"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linting checks"
	@echo "  make format     - Format code and fix linting issues"
	@echo "  make coverage   - Run tests with coverage reporting"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make clean      - Clean build artifacts and coverage reports"
	@echo "  make docs       - Build documentation"
	@echo "  make docs-clean - Clean documentation build artifacts"
	@echo "  make docs-live  - Build documentation with live reload"
	@echo "  make view-docs - Build and open documentation in browser"

test:
	uv run scripts/test.sh

lint:
	uv run scripts/lint.sh

format:
	uv run scripts/format.sh
fmt: format

coverage:
	uv run scripts/coverage.sh

setup:
	./scripts/setup.sh

clean:
	rm -rf build/artifacts/* htmlcov/ .coverage .pytest_cache/ *.egg-info/

docs:
	uv run sphinx-build -b html docs docs/_build/html --keep-going -q

docs-clean:
	rm -rf docs/_build/ docs/api/generated/

docs-live:
	uv run sphinx-autobuild docs docs/_build/html --open-browser

view-docs:
	./scripts/view-docs.sh
