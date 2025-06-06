#!/usr/bin/env bash
# Run linting checks
ruff check .

# Run type checking
mypy glovebox/