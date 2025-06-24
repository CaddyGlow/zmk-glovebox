#!/bin/bash
# Build documentation with Sphinx

set -e

cd "$(dirname "$0")/.."

echo "Building Sphinx documentation..."

# Clean previous build
rm -rf docs/_build/ docs/api/generated/

# Install dependencies if needed
echo "Installing/updating documentation dependencies..."
uv sync

# Build HTML documentation with warnings as non-fatal
echo "Building HTML documentation..."
uv run sphinx-build -b html docs docs/_build/html --keep-going -q

echo "Documentation built successfully!"
echo "Open docs/_build/html/index.html to view the documentation."