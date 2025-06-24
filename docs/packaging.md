# Package Building Scripts

This document describes the package building and distribution system for Glovebox.

## Scripts

### `build.sh`
Builds the package for distribution:
- Cleans previous builds
- Shows git version information
- Creates wheel and source distributions
- Displays build results

### `check-package.sh`
Checks package metadata and readiness:
- Shows package files and sizes
- Displays version information
- Provides PyPI readiness checklist
- Shows testing and publishing commands

### `view-docs.sh`
Builds and opens documentation:
- Builds documentation if not present
- Opens in default browser
- Cross-platform support

## Usage

```bash
# Build package
./scripts/build.sh
# or
make build

# Check package
./scripts/check-package.sh  
# or
make check-package

# View documentation
./scripts/view-docs.sh
# or
make view-docs
```

## Integration

All scripts are integrated with the Makefile for convenient usage:

- `make build` - Build package
- `make check-package` - Check package metadata
- `make publish-test` - Publish to TestPyPI
- `make publish` - Publish to PyPI (with confirmation)

See the main [Makefile](../Makefile) for all available commands.

## Package Configuration

The package uses `uv` for building and `hatch-vcs` for git-based versioning:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"  # Git-based versioning
```

## Version Management

- **Development versions**: `0.1.dev405+gedf98bf.d19800101`
- **Release versions**: Based on git tags (e.g., `v1.0.0` → `1.0.0`)

## Publishing Workflow

1. **Build**: `make build`
2. **Check**: `make check-package`
3. **Test**: `make publish-test` (TestPyPI)
4. **Release**: `make publish` (PyPI)

## Authentication

Configure PyPI tokens for publishing:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-token>
```

Or use uv directly:
```bash
uv publish --username __token__ --password <your-token>
```