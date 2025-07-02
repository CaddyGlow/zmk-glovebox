#!/usr/bin/env bash
set -euo pipefail

# Automatically mark test files based on common patterns
echo "Auto-marking test files based on content patterns..."
echo "=================================================="

# Mark Docker-related tests
echo "Marking Docker tests..."
find tests -name "*.py" -exec grep -l "docker\|Docker\|DockerAdapter" {} \; | while read file; do
    if ! grep -q "pytestmark.*docker" "$file"; then
        echo "Marking $file as docker test"
        sed -i '/^import pytest$/a\\npytestmark = [pytest.mark.docker, pytest.mark.integration]' "$file"
    fi
done

# Mark compilation tests (usually integration tests)
echo "Marking compilation tests..."
find tests -path "*/test_compilation/*" -name "*.py" | while read file; do
    if ! grep -q "pytestmark" "$file"; then
        echo "Marking $file as integration test"
        sed -i '/^import pytest$/a\\npytestmark = pytest.mark.integration' "$file"
    fi
done

# Mark network/API tests
echo "Marking network tests..."
find tests -name "*.py" -exec grep -l "requests\|urllib\|http://\|https://\|api.*call" {} \; | while read file; do
    if ! grep -q "pytestmark.*network" "$file"; then
        echo "Marking $file as network test"
        sed -i '/^import pytest$/a\\npytestmark = [pytest.mark.network, pytest.mark.integration]' "$file"
    fi
done

# Mark CLI integration tests (these tend to be slower)
echo "Marking CLI integration tests..."
find tests -path "*/test_cli/*" -name "*integration*" -name "*.py" | while read file; do
    if ! grep -q "pytestmark" "$file"; then
        echo "Marking $file as integration test"
        sed -i '/^import pytest$/a\\npytestmark = pytest.mark.integration' "$file"
    fi
done

# Mark remaining model tests as unit tests
echo "Marking model tests as unit tests..."
find tests -path "*/test_models*" -name "*.py" | while read file; do
    if ! grep -q "pytestmark" "$file"; then
        echo "Marking $file as unit test"
        sed -i '/^import pytest$/a\\npytestmark = pytest.mark.unit' "$file"
    fi
done

echo ""
echo "Auto-marking completed!"
echo "Run 'make test-fast' to see the effect"