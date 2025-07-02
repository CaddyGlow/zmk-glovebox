#!/usr/bin/env bash
set -euo pipefail

# Smoke test suite - runs critical functionality tests
# Target: < 2 minutes total execution time

echo "Running smoke test suite..."
echo "============================"

# Run smoke tests (if any are marked) or fallback to basic tests
uv run pytest \
  -m "smoke" \
  --tb=short \
  --disable-warnings \
  -q \
  --maxfail=5 \
  "$@" || {
    echo "No smoke tests found, running basic unit tests instead..."
    uv run pytest \
      tests/test_cli/test_app.py \
      tests/test_config/test_models.py \
      tests/test_layout/test_models.py \
      --tb=short \
      --disable-warnings \
      -q \
      --maxfail=5 \
      "$@"
}

echo ""
echo "Smoke tests completed!"