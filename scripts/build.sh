#!/usr/bin/env bash
# Build package for distribution

set -e

cd "$(dirname "$0")/.."

echo "Building Glovebox package for distribution..."

# Show current git tag/version info
if command -v git > /dev/null 2>&1; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "Warning: Working directory has uncommitted changes."
    fi
    
    if git describe --tags --exact-match HEAD > /dev/null 2>&1; then
        echo "Building from git tag: $(git describe --tags --exact-match HEAD)"
    else
        echo "Building from commit: $(git rev-parse --short HEAD)"
    fi
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Build the package
echo "Building package..."
uv build

# Show what was built
echo "Build completed successfully!"
echo "Built packages:"
ls -la dist/

echo ""
echo "To test the package:"
echo "  make check-package # Check package metadata"
echo "  make publish-test  # Publish to TestPyPI"
echo "  make publish       # Publish to PyPI"