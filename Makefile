.PHONY: test lint format fmt coverage setup clean docs docs-clean docs-serve view-docs build check-package publish publish-test help

help:
	@echo "Available commands:"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linting checks"
	@echo "  make format     - Format code and fix linting issues"
	@echo "  make coverage   - Run tests with coverage reporting"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make clean      - Clean build artifacts and coverage reports"
	@echo "  make docs       - Build documentation with MkDocs"
	@echo "  make docs-clean - Clean documentation build artifacts"
	@echo "  make docs-serve - Serve documentation with live reload"
	@echo "  make view-docs  - Instructions for viewing documentation"
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
	rm -rf build/ htmlcov/ .coverage .pytest_cache/ *.egg-info/ dist/ site/

docs:
	uv run mkdocs build

docs-clean:
	rm -rf site/

docs-serve:
	uv run mkdocs serve

view-docs:
	@echo "To view documentation:"
	@echo "1. Run 'make docs' to build"
	@echo "2. Open site/index.html in your browser"
	@echo "Or run 'make docs-serve' for live preview"

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
