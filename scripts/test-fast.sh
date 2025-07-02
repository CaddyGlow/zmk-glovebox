#!/bin/bash
set -euo pipefail

# Fast unit test suite - runs tests that don't require Docker or external services
# Target: < 5 minutes total execution time

echo "🚀 Running fast unit test suite..."
echo "======================================"

# Run only unit tests (exclude integration, slow, docker, network tests)
uv run pytest \
  -m "not integration and not slow and not docker and not network" \
  --tb=short \
  --disable-warnings \
  -q \
  "$@"

echo ""
echo "✅ Fast unit tests completed!"