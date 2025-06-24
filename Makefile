.PHONY: test lint format fmt coverage setup clean docs docs-clean docs-live view-docs build check-package publish publish-test help

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
	@echo "  make build      - Build package for distribution"
	@echo "  make check-package - Check package metadata and readiness"
	@echo "  make publish    - Build and publish package to PyPI"
	@echo "  make publish-test - Build and publish package to TestPyPI"

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
	rm -rf build/ htmlcov/ .coverage .pytest_cache/ *.egg-info/ dist/

docs:
	uv run sphinx-build -b html docs docs/_build/html --keep-going -q

docs-clean:
	rm -rf docs/_build/ docs/api/generated/

docs-live:
	uv run sphinx-autobuild docs docs/_build/html --open-browser

view-docs:
	./scripts/view-docs.sh

build:
	./scripts/build.sh

check-package:
	./scripts/check-package.sh

publish: build
	@echo "Publishing to PyPI..."
	@echo "WARNING: This will publish to the live PyPI repository!"
	@echo "Make sure you want to proceed with this release."
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	uv publish

publish-test: build
	@echo "Publishing to TestPyPI..."
	uv publish --index-url https://test.pypi.org/legacy/
