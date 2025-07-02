#!/usr/bin/env bash
set -euo pipefail

# Full comprehensive test suite - runs ALL tests
# Target: Complete validation (may take 30+ minutes)

echo "Running full comprehensive test suite..."
echo "========================================"

# Check system requirements
echo "Checking system requirements..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "WARNING: Docker not found - some tests will be skipped"
    DOCKER_AVAILABLE=false
else
    if docker info &> /dev/null; then
        echo "Docker is available and running"
        DOCKER_AVAILABLE=true
    else
        echo "WARNING: Docker found but not running - some tests will be skipped"
        DOCKER_AVAILABLE=false
    fi
fi

echo ""
echo "Running all tests with coverage..."

# Run all tests with coverage
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "Running ALL tests (including Docker and slow tests)..."
    uv run pytest \
      --cov=glovebox \
      --cov-report=term-missing \
      --cov-report=xml \
      --cov-report=html \
      --cov-fail-under=80 \
      --tb=short \
      -v \
      "$@"
else
    echo "Running tests (excluding Docker tests)..."
    uv run pytest \
      -m "not docker" \
      --cov=glovebox \
      --cov-report=term-missing \
      --cov-report=xml \
      --cov-report=html \
      --cov-fail-under=80 \
      --tb=short \
      -v \
      "$@"
fi

echo ""
echo "Full test suite completed!"
echo "Coverage report saved to htmlcov/index.html"