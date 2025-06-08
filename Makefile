.PHONY: test lint format fmt coverage setup clean help

help:
	@echo "Available commands:"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linting checks"
	@echo "  make format     - Format code and fix linting issues"
	@echo "  make coverage   - Run tests with coverage reporting"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make clean      - Clean build artifacts and coverage reports"

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
