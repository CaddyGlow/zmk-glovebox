#!/usr/bin/env bash
# Check package metadata and readiness for publication

set -e

cd "$(dirname "$0")/.."

echo "Checking package configuration..."

# Check if package is built
if [ ! -d "dist/" ] || [ -z "$(ls -A dist/)" ]; then
    echo "No built package found. Building package first..."
    make build
fi

echo "Package files in dist/:"
ls -la dist/

echo ""
echo "Checking package metadata..."

# Extract and show package info
if [ -f dist/*.whl ]; then
    echo "Wheel file metadata:"
    uv run python -m wheel unpack dist/*.whl --dest temp_wheel_check > /dev/null 2>&1 || true
    if [ -d temp_wheel_check ]; then
        if [ -f temp_wheel_check/*/METADATA ]; then
            echo "--- METADATA ---"
            head -20 temp_wheel_check/*/METADATA
        fi
        rm -rf temp_wheel_check
    fi
fi

echo ""
echo "PyPI readiness checklist:"
echo "□ Package builds successfully"
echo "□ All tests pass"
echo "□ Version is appropriate (not already published)"
echo "□ README.md is included and properly formatted"
echo "□ License is specified"
echo "□ Dependencies are correctly specified"
echo "□ Entry points are configured"

echo ""
echo "To test the package locally:"
echo "  uv pip install dist/*.whl"
echo ""
echo "To test on TestPyPI:"
echo "  make publish-test"
echo ""
echo "To publish to PyPI:"
echo "  make publish"

# Show current version
echo ""
echo "Current version information:"
if command -v git > /dev/null 2>&1; then
    echo "Git tag: $(git describe --tags --abbrev=0 2>/dev/null || echo 'No tags found')"
    echo "Git commit: $(git rev-parse --short HEAD)"
fi

# Try to get version from package
if [ -f "glovebox/_version.py" ]; then
    echo "Package version: $(python -c 'from glovebox._version import __version__; print(__version__)' 2>/dev/null || echo 'Unable to determine')"
fi