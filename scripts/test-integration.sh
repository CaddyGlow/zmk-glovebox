#!/bin/bash
set -euo pipefail

# Integration test suite - runs tests that may use Docker or external services
# Target: < 15 minutes total execution time

echo "🔧 Running integration test suite..."
echo "===================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found - skipping Docker-dependent tests"
    DOCKER_AVAILABLE=false
else
    if docker info &> /dev/null; then
        echo "✅ Docker is available and running"
        DOCKER_AVAILABLE=true
    else
        echo "⚠️  Docker found but not running - skipping Docker-dependent tests"
        DOCKER_AVAILABLE=false
    fi
fi

# Run integration tests
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "Running all integration tests (including Docker tests)..."
    uv run pytest \
      -m "integration or docker" \
      --tb=short \
      --disable-warnings \
      -v \
      "$@"
else
    echo "Running integration tests (excluding Docker tests)..."
    uv run pytest \
      -m "integration and not docker" \
      --tb=short \
      --disable-warnings \
      -v \
      "$@"
fi

echo ""
echo "✅ Integration tests completed!"