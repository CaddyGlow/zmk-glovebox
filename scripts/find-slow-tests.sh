#!/usr/bin/env bash
set -euo pipefail

# Find slow tests by running pytest with duration reporting
# This helps identify which tests to mark as 'slow' or 'integration'

echo "Running tests with duration reporting to identify slow tests..."
echo "=============================================================="

# Run tests with detailed duration reporting
uv run pytest \
  --durations=50 \
  --tb=no \
  -v \
  --disable-warnings \
  -x \
  --maxfail=1 \
  "$@" | tee test-durations.log

echo ""
echo "Test duration report saved to test-durations.log"
echo "Look for tests taking > 5 seconds to mark as 'slow'"
echo "Look for tests taking > 1 second to mark as 'integration'"